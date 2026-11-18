from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from datetime import timedelta
import uuid

from app.core.database import get_db
from app.core.security import (
    get_password_hash, verify_password, create_access_token, decode_access_token
)
from app.core.deps import get_current_user, record_audit_log
from app.core.config import settings
from app.models.entities import User, UserRole, Notification
from app.schemas.auth import (
    UserRegister, UserLogin, Token, UserResponse, UserUpdate, PasswordResetRequest
)

router = APIRouter(prefix="/auth", tags=["Authentication & Profile"])

class PasswordResetConfirm(BaseModel):
    reset_token: str
    new_password: str = Field(..., min_length=8)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account.
    Security rule: only the initial bootstrap account receives ADMIN; all subsequent
    self-registrations are strictly assigned the standard USER role.
    """
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists"
        )

    user_count = db.query(User).count()
    assigned_role = UserRole.ADMIN.value if user_count == 0 else UserRole.USER.value

    new_user = User(
        id=str(uuid.uuid4()),
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=assigned_role,
        is_active=True,
        is_verified=(user_count == 0)
    )
    db.add(new_user)

    welcome_notif = Notification(
        id=str(uuid.uuid4()),
        user_id=new_user.id,
        title="Welcome to TruthShield AI",
        message=f"Welcome {new_user.full_name}. Account initialized with {assigned_role.upper()} permissions.",
        notification_type="system"
    )
    db.add(welcome_notif)
    db.commit()
    db.refresh(new_user)

    record_audit_log(
        db=db,
        action="user_registered",
        resource_type="user",
        resource_id=new_user.id,
        user_id=new_user.id,
        details={"email": new_user.email, "role": new_user.role}
    )

    return new_user

@router.post("/login", response_model=Token)
def login(login_in: UserLogin, db: Session = Depends(get_db)):
    """Authenticate with email and password to receive a signed JWT token."""
    user = db.query(User).filter(User.email == login_in.email).first()
    if not user or not verify_password(login_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated"
        )

    access_token = create_access_token(
        subject=user.id,
        role=user.role,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    record_audit_log(
        db=db,
        action="user_login_success",
        resource_type="auth",
        resource_id=user.id,
        user_id=user.id,
        details={"email": user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role
        }
    }

@router.post("/password-reset-request")
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    """Generate a short-lived password reset token without leaking account existence."""
    user = db.query(User).filter(User.email == payload.email).first()
    response = {
        "message": "If an account exists for that email, a password reset instruction has been generated."
    }
    if user:
        reset_token = create_access_token(
            subject=user.id,
            role=user.role,
            expires_delta=timedelta(minutes=15),
            extra_claims={"purpose": "password_reset"}
        )
        record_audit_log(
            db=db,
            action="password_reset_requested",
            resource_type="auth",
            resource_id=user.id,
            user_id=user.id,
        )
        if settings.ENV != "production":
            response["dev_reset_token"] = reset_token
    return response

@router.post("/password-reset-confirm")
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    """Verify reset token purpose and update password hash securely."""
    claims = decode_access_token(payload.reset_token)
    if claims.get("purpose") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset token"
        )
    user = db.query(User).filter(User.id == claims.get("sub")).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.hashed_password = get_password_hash(payload.new_password)
    db.commit()

    record_audit_log(
        db=db,
        action="password_reset_completed",
        resource_type="auth",
        resource_id=user.id,
        user_id=user.id,
    )
    return {"message": "Password updated successfully"}

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Return profile details of authenticated user or workspace operator."""
    return current_user

@router.patch("/me", response_model=UserResponse)
def update_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update profile details of authenticated user or workspace operator."""
    if update_data.full_name:
        current_user.full_name = update_data.full_name
    if update_data.password:
        current_user.hashed_password = get_password_hash(update_data.password)

    db.commit()
    db.refresh(current_user)

    record_audit_log(
        db=db,
        action="user_profile_updated",
        resource_type="user",
        resource_id=current_user.id,
        user_id=current_user.id
    )
    return current_user
