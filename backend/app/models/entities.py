import uuid
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey, Index, JSON
)
from sqlalchemy.orm import relationship
from app.core.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)

class UserRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    USER = "user"

class CaseCategory(str, Enum):
    NCII = "ncii"                                    # Non-consensual intimate content
    DEEPFAKE = "deepfake"                            # Deepfake or manipulated media
    IMPERSONATION = "impersonation"                  # Impersonation
    HARASSMENT = "harassment"                        # Harassment
    THREATS = "threats"                              # Threats & intimidation
    MISINFORMATION = "misinformation"                # Fake news and misinformation
    PHISHING = "phishing"                            # Phishing and scam content
    OTHER = "other"                                  # Other harmful content

class CaseStatus(str, Enum):
    DETECTED = "detected"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    REPORT_PREPARED = "report_prepared"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    CONFIRMED_REMOVED = "confirmed_removed"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(32), default=UserRole.USER.value, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    cases = relationship("Case", back_populates="user", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="user", cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisResult", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    fingerprints = relationship("ContentFingerprint", back_populates="user", cascade="all, delete-orphan")

class Case(Base):
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_number = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    category = Column(String(64), nullable=False, index=True)
    description = Column(Text, nullable=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    risk_level = Column(String(32), default=RiskLevel.MEDIUM.value, nullable=False, index=True)
    status = Column(String(64), default=CaseStatus.DETECTED.value, nullable=False, index=True)
    urls = Column(JSON, default=list, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    user = relationship("User", back_populates="cases")
    evidence = relationship("Evidence", back_populates="case", cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisResult", back_populates="case", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="case", cascade="all, delete-orphan")
    removals = relationship("RemovalWorkflow", back_populates="case", cascade="all, delete-orphan")

class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(128), nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)
    evidence_type = Column(String(64), nullable=False) # image, video, audio, text, url_screenshot, document
    description = Column(Text, nullable=True)
    is_sensitive = Column(Boolean, default=False, nullable=False)
    metadata_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    user = relationship("User", back_populates="evidence")
    case = relationship("Case", back_populates="evidence")

class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True)
    content_type = Column(String(32), nullable=False, index=True) # image, video, audio, text, url
    risk_level = Column(String(32), nullable=False, index=True)
    confidence = Column(Float, nullable=False, default=0.0)
    findings = Column(JSON, default=list, nullable=False)
    evidence = Column(JSON, default=list, nullable=False)
    explanation = Column(Text, nullable=False)
    limitations = Column(JSON, default=list, nullable=False)
    recommended_action = Column(Text, nullable=False)
    input_reference = Column(String(512), nullable=True)
    raw_metadata = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    user = relationship("User", back_populates="analysis_results")
    case = relationship("Case", back_populates="analysis_results")

    @property
    def analysis_id(self) -> str:
        return self.id

class ContentFingerprint(Base):
    __tablename__ = "content_fingerprints"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    media_type = Column(String(64), nullable=False) # image, video_frame, audio
    sha256_hash = Column(String(64), nullable=False, index=True)
    phash = Column(String(64), nullable=True, index=True)
    dhash = Column(String(64), nullable=True)
    ahash = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    user = relationship("User", back_populates="fingerprints")

class DuplicateMatch(Base):
    __tablename__ = "duplicate_matches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source_id = Column(String(36), nullable=False, index=True)
    matched_fingerprint_id = Column(String(36), ForeignKey("content_fingerprints.id", ondelete="CASCADE"), nullable=False, index=True)
    similarity_score = Column(Float, nullable=False)
    match_type = Column(String(32), nullable=False) # exact, approximate
    details = Column(JSON, default=dict, nullable=False)
    detected_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    template_type = Column(String(64), nullable=False) # youtube, instagram, facebook, general_web, incident
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    findings_snapshot = Column(JSON, default=dict, nullable=False)
    file_path = Column(String(512), nullable=True)
    status = Column(String(32), default="generated", nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    case = relationship("Case", back_populates="reports")

class RemovalWorkflow(Base):
    __tablename__ = "removal_workflows"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String(64), nullable=False) # youtube, instagram, facebook, reddit, general_web
    violation_type = Column(String(64), nullable=False)
    report_content = Column(Text, nullable=False)
    status = Column(String(64), default="pending_review", nullable=False)
    human_approved = Column(Boolean, default=False, nullable=False)
    approved_by = Column(String(36), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    submission_reference = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    case = relationship("Case", back_populates="removals")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(64), default="system", nullable=False) # case_update, analysis_complete, duplicate_detected, removal_update, system
    is_read = Column(Boolean, default=False, nullable=False)
    case_id = Column(String(36), nullable=True)
    link = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    user = relationship("User", back_populates="notifications")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=True, index=True)
    action = Column(String(128), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(64), nullable=True)
    details = Column(JSON, default=dict, nullable=False)
    ip_address = Column(String(64), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=get_utc_now, nullable=False, index=True)

class AIModelConfig(Base):
    __tablename__ = "ai_model_configs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    model_name = Column(String(128), nullable=False, unique=True)
    provider = Column(String(64), nullable=False) # ollama, local_vision, rule_engine, whisper
    is_active = Column(Boolean, default=True, nullable=False)
    endpoint_url = Column(String(255), nullable=True)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)
