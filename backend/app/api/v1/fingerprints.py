import os
import tempfile
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import cv2
from PIL import Image
from rapidfuzz import fuzz

from app.core.database import get_db
from app.core.deps import get_current_user, record_audit_log
from app.core.config import settings
from app.core.file_validator import inspect_file_magic, UnsafeFileTypeError
from app.api.v1.evidence import read_upload_with_limit
from app.models.entities import User, ContentFingerprint, DuplicateMatch, Notification
from app.schemas.fingerprint import (
    FingerprintResponse, FingerprintMatchResponse
)
from app.services.media.hasher import (
    compute_sha256_from_bytes, compute_perceptual_hashes,
    compute_hamming_distance, calculate_similarity_score
)
from app.services.media.ocr_engine import extract_text_from_image
from app.services.media.audio_analyzer import decode_audio_to_pcm16k, compute_audio_fingerprint

router = APIRouter(prefix="/fingerprints", tags=["Content Fingerprinting & Vault"])

def _extract_video_keyframe_phashes(video_bytes: bytes, suffix: str = ".mp4") -> List[str]:
    """Sample up to 5 keyframes from video bytes and return their pHashes."""
    phashes: List[str] = []
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
        tf.write(video_bytes)
        temp_path = tf.name
    try:
        cap = cv2.VideoCapture(temp_path)
        if cap.isOpened():
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            indices = [int(i * (total - 1) / 4) for i in range(5)] if total > 4 else list(range(max(1, total)))
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if ret and frame is not None:
                    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    h = compute_perceptual_hashes(pil_img)
                    if h.get("phash"):
                        phashes.append(h["phash"])
            cap.release()
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
    return phashes

@router.post("/register", response_model=FingerprintResponse, status_code=status.HTTP_201_CREATED)
async def register_reference_content(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    media_type: str = Form("image"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register user-authorized original reference content (image, video, or audio) to protect against re-uploads.
    Computes SHA-256, perceptual hashes, video frame hashes, audio spectral hashes, and OCR text.
    """
    file_bytes = await read_upload_with_limit(file, settings.MAX_UPLOAD_SIZE_BYTES)
    if len(file_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    try:
        verified_mime, detected_category = inspect_file_magic(file_bytes, file.filename or "asset.bin")
    except UnsafeFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc))

    sha256 = compute_sha256_from_bytes(file_bytes)

    existing = db.query(ContentFingerprint).filter(
        ContentFingerprint.user_id == current_user.id,
        ContentFingerprint.sha256_hash == sha256
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This content is already registered under ID {existing.id} ('{existing.title}')."
        )

    effective_type = detected_category if detected_category in ("image", "video", "audio") else media_type
    phash = dhash = ahash = whash = None
    ocr_text = ""
    frame_phashes: List[str] = []
    audio_fp = ""

    if detected_category == "image":
        hashes = compute_perceptual_hashes(file_bytes)
        phash = hashes.get("phash")
        dhash = hashes.get("dhash")
        ahash = hashes.get("ahash")
        whash = hashes.get("whash")
        ocr_res = extract_text_from_image(file_bytes)
        ocr_text = ocr_res.get("text", "").strip()
    elif detected_category == "video":
        suffix = os.path.splitext(file.filename or ".mp4")[1] or ".mp4"
        frame_phashes = _extract_video_keyframe_phashes(file_bytes, suffix=suffix)
        phash = frame_phashes[0] if frame_phashes else None
    elif detected_category == "audio":
        pcm, _ = decode_audio_to_pcm16k(file_bytes)
        audio_fp = compute_audio_fingerprint(pcm)
        phash = audio_fp or None

    fingerprint = ContentFingerprint(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=title,
        media_type=effective_type,
        sha256_hash=sha256,
        phash=phash,
        dhash=dhash,
        ahash=ahash,
        description=description,
        metadata_json={
            "original_filename": file.filename,
            "size_bytes": len(file_bytes),
            "mime_type": verified_mime,
            "whash": whash,
            "ocr_text": ocr_text[:1000] if ocr_text else "",
            "frame_phashes": frame_phashes,
            "audio_fingerprint": audio_fp,
        },
        created_at=datetime.now(timezone.utc)
    )
    db.add(fingerprint)
    db.commit()
    db.refresh(fingerprint)

    record_audit_log(
        db=db,
        action="fingerprint_registered",
        resource_type="fingerprint",
        resource_id=fingerprint.id,
        user_id=current_user.id,
        details={"sha256": sha256, "phash": phash, "media_type": effective_type}
    )

    return fingerprint

@router.get("", response_model=List[FingerprintResponse])
def list_registered_fingerprints(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all authorized reference content fingerprints owned by user."""
    query = db.query(ContentFingerprint)
    if current_user.role not in ("admin", "analyst"):
        query = query.filter(ContentFingerprint.user_id == current_user.id)

    return query.order_by(ContentFingerprint.created_at.desc()).all()

@router.get("/matches")
def list_duplicate_matches(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve duplicate match detection history."""
    query = db.query(DuplicateMatch).join(
        ContentFingerprint, DuplicateMatch.matched_fingerprint_id == ContentFingerprint.id
    )
    if current_user.role not in ("admin", "analyst"):
        query = query.filter(ContentFingerprint.user_id == current_user.id)

    rows = query.order_by(DuplicateMatch.detected_at.desc()).limit(limit).all()
    output: List[Dict[str, Any]] = []
    for r in rows:
        fp = db.query(ContentFingerprint).filter(ContentFingerprint.id == r.matched_fingerprint_id).first()
        output.append({
            "id": r.id,
            "source_id": r.source_id,
            "matched_fingerprint_id": r.matched_fingerprint_id,
            "matched_title": fp.title if fp else "Deleted Asset",
            "similarity_score": r.similarity_score,
            "match_type": r.match_type,
            "details": r.details,
            "detected_at": r.detected_at.isoformat(),
        })
    return output

@router.post("/search", response_model=List[FingerprintMatchResponse])
async def search_matches(
    file: Optional[UploadFile] = File(None),
    phash: Optional[str] = Form(None),
    sha256: Optional[str] = Form(None),
    ocr_text: Optional[str] = Form(None),
    max_distance: int = Form(10),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search registered reference fingerprints for exact (SHA-256) or approximate
    (perceptual pHash, video keyframe, audio spectral, and OCR text) matches.
    Persists DuplicateMatch records for detected hits.
    """
    target_sha256 = sha256
    target_phash = phash
    target_ocr = (ocr_text or "").strip()
    target_frame_phashes: List[str] = []
    source_label = "hash_query"

    if file:
        file_bytes = await read_upload_with_limit(file, settings.MAX_UPLOAD_SIZE_BYTES)
        if len(file_bytes) == 0:
            raise HTTPException(status_code=400, detail="Uploaded search file is empty")
        try:
            _, detected_category = inspect_file_magic(file_bytes, file.filename or "probe.bin")
        except UnsafeFileTypeError as exc:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc))

        source_label = file.filename or "uploaded_probe"
        target_sha256 = compute_sha256_from_bytes(file_bytes)
        if detected_category == "image":
            hashes = compute_perceptual_hashes(file_bytes)
            target_phash = hashes.get("phash")
            if not target_ocr:
                target_ocr = extract_text_from_image(file_bytes).get("text", "").strip()
        elif detected_category == "video":
            suffix = os.path.splitext(file.filename or ".mp4")[1] or ".mp4"
            target_frame_phashes = _extract_video_keyframe_phashes(file_bytes, suffix=suffix)
            target_phash = target_frame_phashes[0] if target_frame_phashes else None
        elif detected_category == "audio":
            pcm, _ = decode_audio_to_pcm16k(file_bytes)
            target_phash = compute_audio_fingerprint(pcm) or None

    if not target_sha256 and not target_phash and not target_ocr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide an upload file, sha256 hash, phash string, or ocr_text to search."
        )

    query = db.query(ContentFingerprint)
    if current_user.role not in ("admin", "analyst"):
        query = query.filter(ContentFingerprint.user_id == current_user.id)
    candidates = query.all()

    matches: List[FingerprintMatchResponse] = []
    search_run_id = str(uuid.uuid4())

    for item in candidates:
        # 1. Exact SHA-256 match
        if target_sha256 and item.sha256_hash.lower() == target_sha256.lower():
            matches.append(
                FingerprintMatchResponse(
                    id=item.id,
                    title=item.title,
                    media_type=item.media_type,
                    sha256_hash=item.sha256_hash,
                    phash=item.phash,
                    similarity_score=1.0,
                    hamming_distance=0,
                    match_type="exact",
                    created_at=item.created_at
                )
            )
            db.add(DuplicateMatch(
                id=str(uuid.uuid4()),
                source_id=search_run_id,
                matched_fingerprint_id=item.id,
                similarity_score=1.0,
                match_type="exact",
                details={"source_label": source_label, "method": "sha256"},
                detected_at=datetime.now(timezone.utc),
            ))
            continue

        # 2. Approximate perceptual hash match (image, audio, or video frame)
        best_dist = 999
        probe_phashes = target_frame_phashes if target_frame_phashes else ([target_phash] if target_phash else [])
        cand_phashes = (item.metadata_json or {}).get("frame_phashes") or ([item.phash] if item.phash else [])
        for pp in probe_phashes:
            for cp in cand_phashes:
                if pp and cp and len(pp) == len(cp):
                    d = compute_hamming_distance(pp, cp)
                    if d < best_dist:
                        best_dist = d

        if best_dist <= max_distance:
            sim = round(max(0.0, min(1.0, 1.0 - (best_dist / 64.0))), 4)
            matches.append(
                FingerprintMatchResponse(
                    id=item.id,
                    title=item.title,
                    media_type=item.media_type,
                    sha256_hash=item.sha256_hash,
                    phash=item.phash,
                    similarity_score=sim,
                    hamming_distance=best_dist,
                    match_type="approximate",
                    created_at=item.created_at
                )
            )
            db.add(DuplicateMatch(
                id=str(uuid.uuid4()),
                source_id=search_run_id,
                matched_fingerprint_id=item.id,
                similarity_score=sim,
                match_type="approximate",
                details={"source_label": source_label, "method": "perceptual_hash", "hamming_distance": best_dist},
                detected_at=datetime.now(timezone.utc),
            ))
            continue

        # 3. OCR fuzzy text match
        cand_ocr = ((item.metadata_json or {}).get("ocr_text") or "").strip()
        if target_ocr and cand_ocr and len(target_ocr) >= 6 and len(cand_ocr) >= 6:
            ocr_ratio = fuzz.token_set_ratio(target_ocr.lower(), cand_ocr.lower()) / 100.0
            if ocr_ratio >= 0.80:
                matches.append(
                    FingerprintMatchResponse(
                        id=item.id,
                        title=item.title,
                        media_type=item.media_type,
                        sha256_hash=item.sha256_hash,
                        phash=item.phash,
                        similarity_score=round(ocr_ratio, 4),
                        hamming_distance=64,
                        match_type="ocr_text",
                        created_at=item.created_at
                    )
                )
                db.add(DuplicateMatch(
                    id=str(uuid.uuid4()),
                    source_id=search_run_id,
                    matched_fingerprint_id=item.id,
                    similarity_score=round(ocr_ratio, 4),
                    match_type="ocr_text",
                    details={"source_label": source_label, "method": "ocr_fuzzy_match"},
                    detected_at=datetime.now(timezone.utc),
                ))

    if matches:
        db.add(Notification(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            title="Vault Search Matched Reference Content",
            message=f"Probe '{source_label}' matched {len(matches)} protected reference asset(s).",
            notification_type="duplicate_detected",
        ))
        db.commit()

    matches.sort(key=lambda m: m.similarity_score, reverse=True)
    return matches

@router.delete("/{fingerprint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fingerprint(
    fingerprint_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a reference fingerprint from the vault."""
    fp = db.query(ContentFingerprint).filter(ContentFingerprint.id == fingerprint_id).first()
    if not fp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fingerprint not found")
    if current_user.role not in ("admin", "analyst") and fp.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    record_audit_log(
        db=db,
        action="fingerprint_deleted",
        resource_type="fingerprint",
        resource_id=fp.id,
        user_id=current_user.id,
        details={"title": fp.title}
    )
    db.delete(fp)
    db.commit()
    return None
