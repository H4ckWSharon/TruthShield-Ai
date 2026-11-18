import os
import uuid
import re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.deps import get_current_user, record_audit_log
from app.core.config import settings
from app.core.encryption import encrypt_evidence_bytes, decrypt_evidence_bytes, secure_shred_file
from app.core.file_validator import inspect_file_magic, UnsafeFileTypeError
from app.models.entities import (
    User, Case, Evidence, ContentFingerprint, DuplicateMatch, Notification
)
from app.schemas.evidence import EvidenceResponse
from app.services.media.hasher import (
    compute_sha256_from_bytes, compute_perceptual_hashes,
    compute_hamming_distance, calculate_similarity_score
)

router = APIRouter(prefix="/evidence", tags=["Evidence Vault"])

def sanitize_filename(filename: str) -> str:
    """Strip path traversal characters and normalize file base name."""
    clean = re.sub(r"[^\w\.-]", "_", Path(filename).name)
    return clean or "unnamed_file"

async def read_upload_with_limit(upload: UploadFile, max_bytes: int) -> bytes:
    """Stream upload in 64KB chunks and enforce strict size cap before full allocation."""
    chunks: List[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size ({max_bytes // (1024 * 1024)}MB)"
            )
        chunks.append(chunk)
    return b"".join(chunks)

@router.post("/upload", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    file: UploadFile = File(...),
    case_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_sensitive: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Securely upload digital evidence into encrypted, isolated storage vault.
    Validates magic-byte file signatures, encrypts bytes at rest (Fernet),
    computes SHA-256 & perceptual hashes, and checks for duplicate reference matches.
    """
    if case_id:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated case not found")
        if current_user.role not in ("admin", "analyst") and case.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot attach evidence to unauthorized case")

    file_bytes = await read_upload_with_limit(file, settings.MAX_UPLOAD_SIZE_BYTES)
    file_size = len(file_bytes)
    if file_size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    clean_filename = sanitize_filename(file.filename or "evidence.bin")

    # Magic-byte verification (never trust client Content-Type header)
    try:
        verified_mime, ev_type = inspect_file_magic(file_bytes, clean_filename)
    except UnsafeFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc)
        )

    sha256 = compute_sha256_from_bytes(file_bytes)
    stored_name = f"{uuid.uuid4().hex}_{clean_filename}.enc"
    storage_path = settings.EVIDENCE_DIR / stored_name

    # Encrypt payload at rest before persisting to disk
    encrypted_bytes = encrypt_evidence_bytes(file_bytes)
    with open(storage_path, "wb") as f:
        f.write(encrypted_bytes)

    if ev_type == "image":
        metadata_json = compute_perceptual_hashes(file_bytes)
    elif ev_type == "video":
        metadata_json = {"container_mime": verified_mime}
    elif ev_type == "audio":
        metadata_json = {"audio_mime": verified_mime}
    else:
        metadata_json = {"mime": verified_mime}

    metadata_json["encrypted_at_rest"] = True

    evidence_id = str(uuid.uuid4())
    evidence = Evidence(
        id=evidence_id,
        case_id=case_id,
        user_id=current_user.id,
        original_filename=clean_filename,
        stored_filename=stored_name,
        file_path=str(storage_path),
        file_size=file_size,
        mime_type=verified_mime,
        sha256_hash=sha256,
        evidence_type=ev_type,
        description=description,
        is_sensitive=is_sensitive,
        metadata_json=metadata_json
    )
    db.add(evidence)

    # Automatic Re-Upload Monitoring against authorized Reference Fingerprints
    if settings.ENABLE_FINGERPRINTING:
        phash_val = metadata_json.get("phash") if ev_type == "image" else None
        candidates = db.query(ContentFingerprint).all()
        for fp in candidates:
            if current_user.role not in ("admin", "analyst") and fp.user_id != current_user.id:
                continue
            matched = False
            match_type = "exact"
            sim_score = 1.0
            if fp.sha256_hash.lower() == sha256.lower():
                matched = True
            elif phash_val and fp.phash:
                dist = compute_hamming_distance(phash_val, fp.phash)
                if dist <= 8:
                    matched = True
                    match_type = "approximate"
                    sim_score = calculate_similarity_score(phash_val, fp.phash)

            if matched:
                dup = DuplicateMatch(
                    id=str(uuid.uuid4()),
                    source_id=evidence_id,
                    matched_fingerprint_id=fp.id,
                    similarity_score=sim_score,
                    match_type=match_type,
                    details={
                        "evidence_filename": clean_filename,
                        "case_id": case_id,
                        "sha256": sha256,
                    },
                    detected_at=datetime.now(timezone.utc),
                )
                db.add(dup)
                notif = Notification(
                    id=str(uuid.uuid4()),
                    user_id=current_user.id,
                    title=f"Re-Upload Match Detected ({match_type.upper()})",
                    message=f"Uploaded evidence '{clean_filename}' matched protected asset '{fp.title}' ({int(sim_score * 100)}% similarity).",
                    notification_type="duplicate_detected",
                    case_id=case_id,
                )
                db.add(notif)

    db.commit()
    db.refresh(evidence)

    record_audit_log(
        db=db,
        action="evidence_uploaded",
        resource_type="evidence",
        resource_id=evidence.id,
        user_id=current_user.id,
        details={
            "sha256": sha256,
            "file_size": file_size,
            "verified_mime": verified_mime,
            "case_id": case_id,
            "is_sensitive": is_sensitive,
        }
    )

    return evidence

@router.get("", response_model=List[EvidenceResponse])
def list_evidence(
    case_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List evidence records visible to current operator, optionally filtered by case_id."""
    query = db.query(Evidence)
    if current_user.role not in ("admin", "analyst"):
        query = query.filter(Evidence.user_id == current_user.id)
    if case_id:
        query = query.filter(Evidence.case_id == case_id)
    return query.order_by(Evidence.created_at.desc()).all()

@router.get("/{evidence_id}", response_model=EvidenceResponse)
def get_evidence_metadata(
    evidence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve metadata and cryptographic hash for an evidence asset."""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence item not found")

    if current_user.role not in ("admin", "analyst") and evidence.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return evidence

@router.get("/{evidence_id}/download")
def download_evidence(
    evidence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Securely decrypt and stream evidence file with authorization check."""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence item not found")

    if current_user.role not in ("admin", "analyst") and evidence.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if not os.path.exists(evidence.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence file missing on disk")

    with open(evidence.file_path, "rb") as f:
        stored_bytes = f.read()

    plaintext_bytes = decrypt_evidence_bytes(stored_bytes)

    record_audit_log(
        db=db,
        action="evidence_downloaded",
        resource_type="evidence",
        resource_id=evidence.id,
        user_id=current_user.id
    )

    return Response(
        content=plaintext_bytes,
        media_type=evidence.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{evidence.original_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )

@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence(
    evidence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Securely shred and permanently delete an evidence asset from vault and database."""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence item not found")

    if current_user.role not in ("admin", "analyst") and evidence.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    secure_shred_file(evidence.file_path)

    record_audit_log(
        db=db,
        action="evidence_shredded_deleted",
        resource_type="evidence",
        resource_id=evidence.id,
        user_id=current_user.id,
        details={"sha256": evidence.sha256_hash}
    )

    db.delete(evidence)
    db.commit()
    return None
