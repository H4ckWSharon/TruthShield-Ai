import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.deps import get_current_user, record_audit_log
from app.core.config import settings
from app.core.file_validator import inspect_file_magic, UnsafeFileTypeError
from app.api.v1.evidence import read_upload_with_limit
from app.models.entities import User, AnalysisResult, Notification, RiskLevel
from app.schemas.analysis import (
    TextAnalysisRequest, URLAnalysisRequest, AnalysisResponse
)
from app.services.ai.orchestrator import orchestrator
from app.services.media.url_analyzer import SSRFSecurityViolation

router = APIRouter(prefix="/analysis", tags=["Multimodal AI Analysis"])

def save_analysis_record(
    db: Session,
    user_id: str,
    result: dict,
    case_id: Optional[str] = None
) -> AnalysisResult:
    """Persist structured analysis findings to database."""
    record = AnalysisResult(
        id=result["analysis_id"],
        user_id=user_id,
        case_id=case_id,
        content_type=result["content_type"],
        risk_level=result["risk_level"],
        confidence=result["confidence"],
        findings=result["findings"],
        evidence=result["evidence"],
        explanation=result["explanation"],
        limitations=result["limitations"],
        recommended_action=result["recommended_action"],
        input_reference=result.get("input_reference"),
        raw_metadata=result.get("raw_metadata", {}),
        created_at=datetime.now(timezone.utc)
    )
    db.add(record)

    if result["risk_level"] in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value):
        notif = Notification(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=f"High Risk Content Flagged ({result['content_type'].upper()})",
            message=f"Analysis flagged {result['risk_level'].upper()} risk (Confidence: {int(result['confidence']*100)}%).",
            notification_type="analysis_complete",
            case_id=case_id
        )
        db.add(notif)

    db.commit()
    db.refresh(record)
    return record

@router.post("/text", response_model=AnalysisResponse)
async def analyze_text(
    payload: TextAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze textual content for threats, harassment, extortion, or impersonation."""
    result = await orchestrator.execute_analysis(
        content_type="text",
        data=payload.text,
        context={"context_type": payload.context_type},
        db=db,
    )
    record = save_analysis_record(db, current_user.id, result, payload.case_id)

    record_audit_log(
        db=db,
        action="text_analyzed",
        resource_type="analysis",
        resource_id=record.id,
        user_id=current_user.id,
        details={"risk_level": record.risk_level}
    )
    return record

@router.post("/url", response_model=AnalysisResponse)
async def analyze_url(
    payload: URLAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Forensic URL inspection with strict SSRF protection against internal network destinations."""
    try:
        result = await orchestrator.execute_analysis(
            content_type="url",
            data=payload.url,
            db=db,
        )
    except SSRFSecurityViolation as e:
        record_audit_log(
            db=db,
            action="ssrf_blocked",
            resource_type="security",
            user_id=current_user.id,
            details={"blocked_url": payload.url, "reason": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SSRF Protection Alert: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    record = save_analysis_record(db, current_user.id, result, payload.case_id)
    record_audit_log(
        db=db,
        action="url_analyzed",
        resource_type="analysis",
        resource_id=record.id,
        user_id=current_user.id,
        details={"url": payload.url, "risk_level": record.risk_level}
    )
    return record

@router.post("/image", response_model=AnalysisResponse)
async def analyze_image(
    file: UploadFile = File(...),
    case_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze image media for perceptual hashes, metadata, OCR threats, ELA, and visual heuristics."""
    file_bytes = await read_upload_with_limit(file, settings.MAX_UPLOAD_SIZE_BYTES)
    if len(file_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file uploaded")

    try:
        _, category = inspect_file_magic(file_bytes, file.filename or "upload.jpg")
        if category != "image":
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File signature is not a supported image format")
    except UnsafeFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc))

    result = await orchestrator.execute_analysis(
        content_type="image",
        data=file_bytes,
        filename=file.filename or "upload.jpg",
        db=db,
    )
    record = save_analysis_record(db, current_user.id, result, case_id)
    record_audit_log(
        db=db,
        action="image_analyzed",
        resource_type="analysis",
        resource_id=record.id,
        user_id=current_user.id,
        details={"filename": file.filename, "risk_level": record.risk_level}
    )
    return record

@router.post("/video", response_model=AnalysisResponse)
async def analyze_video(
    file: UploadFile = File(...),
    case_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze video media with OpenCV keyframes, frame OCR, and FFmpeg/Whisper audio transcription."""
    file_bytes = await read_upload_with_limit(file, settings.MAX_UPLOAD_SIZE_BYTES)
    if len(file_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty video file uploaded")

    try:
        _, category = inspect_file_magic(file_bytes, file.filename or "upload.mp4")
        if category != "video":
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File signature is not a supported video format")
    except UnsafeFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc))

    result = await orchestrator.execute_analysis(
        content_type="video",
        data=file_bytes,
        filename=file.filename or "upload.mp4",
        db=db,
    )
    record = save_analysis_record(db, current_user.id, result, case_id)
    record_audit_log(
        db=db,
        action="video_analyzed",
        resource_type="analysis",
        resource_id=record.id,
        user_id=current_user.id,
        details={"filename": file.filename, "risk_level": record.risk_level}
    )
    return record

@router.post("/audio", response_model=AnalysisResponse)
async def analyze_audio(
    file: UploadFile = File(...),
    case_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze audio media with PyAV decoding, Whisper speech transcription, and threat scanning."""
    file_bytes = await read_upload_with_limit(file, settings.MAX_UPLOAD_SIZE_BYTES)
    if len(file_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio file uploaded")

    try:
        _, category = inspect_file_magic(file_bytes, file.filename or "upload.wav")
        if category != "audio":
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File signature is not a supported audio format")
    except UnsafeFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc))

    result = await orchestrator.execute_analysis(
        content_type="audio",
        data=file_bytes,
        filename=file.filename or "upload.wav",
        db=db,
    )
    record = save_analysis_record(db, current_user.id, result, case_id)
    record_audit_log(
        db=db,
        action="audio_analyzed",
        resource_type="analysis",
        resource_id=record.id,
        user_id=current_user.id,
        details={"filename": file.filename, "risk_level": record.risk_level}
    )
    return record

@router.get("/{analysis_id}", response_model=AnalysisResponse)
def get_analysis_by_id(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve full analysis report by ID."""
    record = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis record not found")

    if current_user.role not in ("admin", "analyst") and record.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return record
