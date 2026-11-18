from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
import uuid

from app.core.database import get_db
from app.core.deps import require_role, record_audit_log
from app.core.config import settings
from app.models.entities import User, UserRole, Case, AIModelConfig, AuditLog
from app.schemas.admin import (
    SystemHealthResponse, UserAdminView, UserRoleUpdate, AIModelConfigItem, AIModelToggleRequest
)
from app.services.ai.orchestrator import orchestrator
from app.workers.celery_app import is_redis_available

router = APIRouter(prefix="/admin", tags=["Admin Command Center"])

admin_required = require_role(["admin"])

@router.get("/system-health", response_model=SystemHealthResponse)
async def get_system_health(
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """Real-time system health audit, database connectivity, Redis worker probe, and Ollama check."""
    ollama_info = await orchestrator.check_ollama_status(db=db)
    ollama_status_str = ollama_info["status"]
    redis_status_str = "connected" if is_redis_available() else "in_process_fallback"

    db_status = "operational"
    try:
        total_cases = db.query(Case).count()
        total_users = db.query(User).count()
    except Exception:
        db_status = "degraded"
        total_cases = 0
        total_users = 0

    storage_ok = settings.STORAGE_DIR.exists() and settings.EVIDENCE_DIR.exists()

    return SystemHealthResponse(
        status="operational" if db_status == "operational" and storage_ok else "degraded",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        company=settings.COMPANY_NAME,
        environment=settings.ENV,
        database_status=db_status,
        ollama_status=ollama_status_str,
        redis_status=redis_status_str,
        storage_accessible=storage_ok,
        active_cases=total_cases,
        total_users=total_users,
        system_time=datetime.now(timezone.utc)
    )

@router.get("/users", response_model=List[UserAdminView])
def list_all_users(
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """List all registered users with role status and case metrics."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    results = []
    for u in users:
        case_cnt = db.query(Case).filter(Case.user_id == u.id).count()
        results.append(
            UserAdminView(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                role=u.role,
                is_active=u.is_active,
                is_verified=u.is_verified,
                created_at=u.created_at,
                case_count=case_cnt
            )
        )
    return results

@router.patch("/users/{user_id}", response_model=UserAdminView)
def update_user_role_or_status(
    user_id: str,
    payload: UserRoleUpdate,
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """Modify user role (admin, analyst, user) or active status safely."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.role is not None:
        if payload.role not in [r.value for r in UserRole]:
            raise HTTPException(status_code=400, detail="Invalid role value")
        if user.id == current_user.id and payload.role != "admin":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot demote your own admin account")
        user.role = payload.role

    if payload.is_active is not None:
        if user.id == current_user.id and not payload.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot disable your own admin account")
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)

    record_audit_log(
        db=db,
        action="user_role_modified_by_admin",
        resource_type="user",
        resource_id=user.id,
        user_id=current_user.id,
        details={"new_role": user.role, "is_active": user.is_active}
    )

    case_cnt = db.query(Case).filter(Case.user_id == user.id).count()
    return UserAdminView(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        case_count=case_cnt
    )

@router.get("/models", response_model=List[AIModelConfigItem])
def list_ai_models(
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """List configurable AI and media models."""
    configs = db.query(AIModelConfig).all()
    if not configs:
        defaults = [
            AIModelConfig(
                id=str(uuid.uuid4()),
                model_name=settings.OLLAMA_MODEL,
                provider="ollama",
                is_active=settings.ENABLE_OLLAMA,
                endpoint_url=settings.OLLAMA_BASE_URL,
                description="Local Large Language Model for deep semantic policy verification."
            ),
            AIModelConfig(
                id=str(uuid.uuid4()),
                model_name="rule_based_heuristics",
                provider="rule_engine",
                is_active=True,
                endpoint_url="internal",
                description="Deterministic lexical, OCR, ELA, and chrominance scoring engine."
            ),
            AIModelConfig(
                id=str(uuid.uuid4()),
                model_name="perceptual_hasher_suite",
                provider="local_vision",
                is_active=True,
                endpoint_url="internal",
                description="pHash, dHash, aHash, and RapidOCR fingerprinting suite."
            ),
            AIModelConfig(
                id=str(uuid.uuid4()),
                model_name=f"faster_whisper_{settings.WHISPER_MODEL_SIZE}",
                provider="whisper",
                is_active=settings.ENABLE_AUDIO_TRANSCRIPTION,
                endpoint_url="internal",
                description="Local Faster-Whisper speech-to-text forensic pipeline."
            )
        ]
        for d in defaults:
            db.add(d)
        db.commit()
        configs = db.query(AIModelConfig).all()

    return configs

@router.patch("/models/{model_id}", response_model=AIModelConfigItem)
def toggle_ai_model(
    model_id: str,
    payload: AIModelToggleRequest,
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """Enable or disable AI model provider."""
    model_cfg = db.query(AIModelConfig).filter(AIModelConfig.id == model_id).first()
    if not model_cfg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI Model configuration not found")

    model_cfg.is_active = payload.is_active
    if payload.endpoint_url:
        model_cfg.endpoint_url = payload.endpoint_url

    model_cfg.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(model_cfg)

    record_audit_log(
        db=db,
        action="ai_model_config_updated",
        resource_type="model_config",
        resource_id=model_cfg.id,
        user_id=current_user.id,
        details={"model_name": model_cfg.model_name, "is_active": model_cfg.is_active}
    )

    return model_cfg

@router.get("/audit-logs")
def get_audit_logs(
    limit: int = 100,
    current_user: User = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """Retrieve immutable security audit trail."""
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "details": l.details,
            "ip_address": l.ip_address,
            "timestamp": l.timestamp.isoformat()
        }
        for l in logs
    ]
