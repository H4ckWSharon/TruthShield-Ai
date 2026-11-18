from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from typing import Optional
from datetime import datetime, timezone
import uuid

from app.core.database import get_db
from app.core.deps import get_current_user, record_audit_log
from app.models.entities import (
    User, Case, CaseCategory, CaseStatus, RiskLevel, Evidence,
    AnalysisResult, Report, RemovalWorkflow, Notification
)
from app.schemas.case import CaseCreate, CaseUpdate, CaseResponse, CaseListResponse

router = APIRouter(prefix="/cases", tags=["Case Management"])

def generate_case_number(db: Session) -> str:
    """Generate monotonically increasing case identifier e.g., TSA-2026-0042 without deletion collisions."""
    year = datetime.now(timezone.utc).year
    prefix = f"TSA-{year}-"
    existing_numbers = (
        db.query(Case.case_number)
        .filter(Case.case_number.like(f"{prefix}%"))
        .all()
    )
    max_seq = 0
    for (num_str,) in existing_numbers:
        try:
            seq = int(num_str.split("-")[-1])
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue
    return f"{prefix}{max_seq + 1:04d}"

@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    case_in: CaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new digital content protection investigation case."""
    valid_categories = [c.value for c in CaseCategory]
    if case_in.category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category '{case_in.category}'. Allowed: {', '.join(valid_categories)}"
        )

    new_case = None
    for attempt in range(5):
        case_num = generate_case_number(db)
        if attempt > 0:
            # Disambiguate on concurrent collision
            case_num = f"{case_num}-{uuid.uuid4().hex[:4].upper()}"
        candidate = Case(
            id=str(uuid.uuid4()),
            case_number=case_num,
            title=case_in.title,
            category=case_in.category,
            description=case_in.description,
            user_id=current_user.id,
            risk_level=case_in.risk_level or RiskLevel.MEDIUM.value,
            status=CaseStatus.DETECTED.value,
            urls=case_in.urls or [],
            notes=case_in.notes or "",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(candidate)
        try:
            db.flush()
            new_case = candidate
            break
        except IntegrityError:
            db.rollback()
            continue

    if new_case is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to allocate unique case number"
        )

    notif = Notification(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=f"Case Registered: {new_case.case_number}",
        message=f"Investigation case '{new_case.title}' ({new_case.category.upper()}) was opened.",
        notification_type="case_update",
        case_id=new_case.id
    )
    db.add(notif)
    db.commit()
    db.refresh(new_case)

    record_audit_log(
        db=db,
        action="case_created",
        resource_type="case",
        resource_id=new_case.id,
        user_id=current_user.id,
        details={"case_number": new_case.case_number, "category": new_case.category}
    )

    new_case.evidence_count = 0
    return new_case

@router.get("", response_model=CaseListResponse)
def list_cases(
    status_filter: Optional[str] = Query(None, alias="status"),
    category_filter: Optional[str] = Query(None, alias="category"),
    risk_filter: Optional[str] = Query(None, alias="risk_level"),
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve investigation cases with multi-criteria filtering and keyword search."""
    query = db.query(Case)
    if current_user.role not in ("admin", "analyst"):
        query = query.filter(Case.user_id == current_user.id)

    if status_filter:
        query = query.filter(Case.status == status_filter)
    if category_filter:
        query = query.filter(Case.category == category_filter)
    if risk_filter:
        query = query.filter(Case.risk_level == risk_filter)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Case.title.ilike(search_pattern),
                Case.case_number.ilike(search_pattern),
                Case.description.ilike(search_pattern)
            )
        )

    total = query.count()
    cases = query.order_by(Case.created_at.desc()).offset(skip).limit(limit).all()

    for c in cases:
        c.evidence_count = db.query(Evidence).filter(Evidence.case_id == c.id).count()

    return CaseListResponse(items=cases, total=total)

@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get single investigation case by ID."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if current_user.role not in ("admin", "analyst") and case.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    case.evidence_count = db.query(Evidence).filter(Evidence.case_id == case.id).count()
    return case

@router.get("/{case_id}/export")
def export_case_bundle(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export complete forensic JSON dossier for an investigation case."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if current_user.role not in ("admin", "analyst") and case.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    evidences = db.query(Evidence).filter(Evidence.case_id == case.id).all()
    analyses = db.query(AnalysisResult).filter(AnalysisResult.case_id == case.id).all()
    reports = db.query(Report).filter(Report.case_id == case.id).all()
    removals = db.query(RemovalWorkflow).filter(RemovalWorkflow.case_id == case.id).all()

    record_audit_log(
        db=db,
        action="case_exported",
        resource_type="case",
        resource_id=case.id,
        user_id=current_user.id,
        details={"case_number": case.case_number}
    )

    return {
        "case": {
            "id": case.id,
            "case_number": case.case_number,
            "title": case.title,
            "category": case.category,
            "description": case.description,
            "risk_level": case.risk_level,
            "status": case.status,
            "urls": case.urls,
            "notes": case.notes,
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
        },
        "evidence": [
            {
                "id": ev.id,
                "original_filename": ev.original_filename,
                "mime_type": ev.mime_type,
                "file_size": ev.file_size,
                "sha256_hash": ev.sha256_hash,
                "evidence_type": ev.evidence_type,
                "is_sensitive": ev.is_sensitive,
                "metadata_json": ev.metadata_json,
                "created_at": ev.created_at.isoformat(),
            }
            for ev in evidences
        ],
        "analyses": [
            {
                "analysis_id": a.id,
                "content_type": a.content_type,
                "risk_level": a.risk_level,
                "confidence": a.confidence,
                "findings": a.findings,
                "explanation": a.explanation,
                "created_at": a.created_at.isoformat(),
            }
            for a in analyses
        ],
        "reports": [
            {
                "id": r.id,
                "template_type": r.template_type,
                "title": r.title,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in reports
        ],
        "removal_workflows": [
            {
                "id": w.id,
                "platform": w.platform,
                "violation_type": w.violation_type,
                "status": w.status,
                "human_approved": w.human_approved,
                "submission_reference": w.submission_reference,
                "updated_at": w.updated_at.isoformat(),
            }
            for w in removals
        ],
    }

@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: str,
    case_in: CaseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update case status, title, category, description, risk level, notes, or URLs."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if current_user.role not in ("admin", "analyst") and case.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    status_changed = False
    old_status = case.status

    if case_in.title is not None:
        case.title = case_in.title
    if case_in.category is not None:
        valid_categories = [c.value for c in CaseCategory]
        if case_in.category not in valid_categories:
            raise HTTPException(status_code=400, detail=f"Invalid category '{case_in.category}'")
        case.category = case_in.category
    if case_in.description is not None:
        case.description = case_in.description
    if case_in.risk_level is not None:
        case.risk_level = case_in.risk_level
    if case_in.status is not None and case_in.status != case.status:
        valid_statuses = [s.value for s in CaseStatus]
        if case_in.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status '{case_in.status}'")
        case.status = case_in.status
        status_changed = True
    if case_in.urls is not None:
        case.urls = case_in.urls
    if case_in.notes is not None:
        case.notes = case_in.notes

    case.updated_at = datetime.now(timezone.utc)

    if status_changed:
        notif = Notification(
            id=str(uuid.uuid4()),
            user_id=case.user_id,
            title=f"Case Status Updated: {case.case_number}",
            message=f"Status changed from {old_status.upper()} to {case.status.upper()}.",
            notification_type="case_update",
            case_id=case.id
        )
        db.add(notif)

    db.commit()
    db.refresh(case)

    record_audit_log(
        db=db,
        action="case_updated",
        resource_type="case",
        resource_id=case.id,
        user_id=current_user.id,
        details={"status": case.status, "risk_level": case.risk_level}
    )

    case.evidence_count = db.query(Evidence).filter(Evidence.case_id == case.id).count()
    return case

@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an investigation case and associated evidence links."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if current_user.role not in ("admin", "analyst") and case.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    record_audit_log(
        db=db,
        action="case_deleted",
        resource_type="case",
        resource_id=case.id,
        user_id=current_user.id,
        details={"case_number": case.case_number}
    )

    db.delete(case)
    db.commit()
    return None
