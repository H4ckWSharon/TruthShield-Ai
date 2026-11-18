from contextvars import ContextVar
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
import uuid

from app.core.database import get_db
from app.core.config import settings
from app.core.security import decode_access_token, get_password_hash
from app.models.entities import User, UserRole, AuditLog

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

_request_ip_ctx: ContextVar[str] = ContextVar("request_ip", default="127.0.0.1")

def set_request_ip(ip: str) -> None:
    _request_ip_ctx.set(ip or "127.0.0.1")

def get_request_ip() -> str:
    return _request_ip_ctx.get()

def get_or_create_workspace_operator(db: Session) -> User:
    """Resolve or provision the default workspace operator when operating without login/signup."""
    operator = (
        db.query(User)
        .filter(User.role == UserRole.ADMIN.value, User.is_active == True)
        .order_by(User.created_at.asc())
        .first()
    )
    if operator:
        return operator

    operator = db.query(User).filter(User.email == "operator@truthshield.com").first()
    if operator:
        if not operator.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace operator account has been deactivated",
            )
        return operator

    operator = User(
        id=str(uuid.uuid4()),
        email="operator@truthshield.com",
        hashed_password=get_password_hash(uuid.uuid4().hex + "!Ts2026"),
        full_name="Workspace Security Officer",
        role=UserRole.ADMIN.value,
        is_active=True,
        is_verified=True,
    )
    db.add(operator)
    db.commit()
    db.refresh(operator)
    return operator

def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Validate JWT token if supplied, or auto-resolve workspace operator when REQUIRE_AUTH=False.
    """
    if not token:
        if settings.REQUIRE_AUTH:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials were not provided",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return get_or_create_workspace_operator(db)

    payload = decode_access_token(token)
    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account associated with this token no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been deactivated",
        )
    return user

def require_role(allowed_roles: List[str]):
    """Dependency factory for Role-Based Access Control."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}. Current role: {current_user.role}"
            )
        return current_user
    return role_checker

def record_audit_log(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    user_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    """Create an immutable security audit log entry capturing real request IP."""
    resolved_ip = ip_address or get_request_ip()
    log_entry = AuditLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=resolved_ip,
        timestamp=datetime.now(timezone.utc)
    )
    db.add(log_entry)
    db.commit()
    return log_entry
