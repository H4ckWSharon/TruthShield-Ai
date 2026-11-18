import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.deps import get_current_user, record_audit_log
from app.core.config import settings
from app.models.entities import User, Case, Evidence, AnalysisResult, Report, Notification
from app.schemas.report import ReportCreate, ReportResponse
from app.services.reports.pdf_generator import generate_pdf_report

router = APIRouter(prefix="/reports", tags=["Report Generation Engine"])

@router.post("/generate", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compile and render a tamper-evident, evidence-based PDF investigation report
    with Alphard Crucis Private Limited & TruthShield AI branding.
    """
    case = db.query(Case).filter(Case.id == payload.case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if current_user.role not in ("admin", "analyst") and case.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Gather case evidence and analysis results
    evidence_items = db.query(Evidence).filter(Evidence.case_id == case.id).all()
    analysis_items = db.query(AnalysisResult).filter(AnalysisResult.case_id == case.id).all()

    evidence_list = [
        {
            "original_filename": ev.original_filename,
            "evidence_type": ev.evidence_type,
            "sha256_hash": ev.sha256_hash,
            "file_size": ev.file_size
        }
        for ev in evidence_items
    ]

    analysis_list = [
        {
            "content_type": a.content_type,
            "risk_level": a.risk_level,
            "confidence": a.confidence,
            "explanation": a.explanation
        }
        for a in analysis_items
    ]

    case_dict = {
        "case_number": case.case_number,
        "title": case.title,
        "category": case.category,
        "status": case.status,
        "risk_level": case.risk_level,
        "description": case.description,
        "urls": case.urls or []
    }

    # Generate the physical PDF file
    report_title = payload.title or f"Incident Report: {case.case_number} ({payload.template_type.upper()})"
    pdf_filename = f"TruthShield_Report_{case.case_number.replace('-', '_')}_{uuid.uuid4().hex[:6]}.pdf"
    
    try:
        pdf_path = generate_pdf_report(
            case_data=case_dict,
            template_type=payload.template_type,
            evidence_list=evidence_list,
            analysis_list=analysis_list,
            output_filename=pdf_filename
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {str(e)}"
        )

    # Persist report entity
    report = Report(
        id=str(uuid.uuid4()),
        case_id=case.id,
        user_id=current_user.id,
        template_type=payload.template_type,
        title=report_title,
        summary=payload.summary or f"Official platform violation report compiled for case {case.case_number}.",
        findings_snapshot={
            "evidence_count": len(evidence_list),
            "analysis_count": len(analysis_list),
            "case_number": case.case_number
        },
        file_path=pdf_path,
        status="generated",
        created_at=datetime.now(timezone.utc)
    )
    db.add(report)

    # Update case status if in early stage
    if case.status in ("detected", "pending_verification", "verified"):
        case.status = "report_prepared"
        case.updated_at = datetime.now(timezone.utc)

    # Notification
    notif = Notification(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=f"Report Generated: {case.case_number}",
        message=f"Forensic PDF report ({payload.template_type.upper()}) is ready for download.",
        notification_type="system",
        case_id=case.id
    )
    db.add(notif)
    db.commit()
    db.refresh(report)

    record_audit_log(
        db=db,
        action="report_generated",
        resource_type="report",
        resource_id=report.id,
        user_id=current_user.id,
        details={"case_id": case.id, "template": payload.template_type}
    )

    return report

@router.get("", response_model=List[ReportResponse])
def list_reports(
    case_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List reports for current user or specific case."""
    query = db.query(Report)
    if current_user.role not in ("admin", "analyst"):
        query = query.filter(Report.user_id == current_user.id)
    if case_id:
        query = query.filter(Report.case_id == case_id)
        
    return query.order_by(Report.created_at.desc()).all()

@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get metadata for a report."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        
    if current_user.role not in ("admin", "analyst") and report.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
    return report

@router.get("/{report_id}/download")
def download_pdf_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download the generated PDF report."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        
    if current_user.role not in ("admin", "analyst") and report.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF report file missing on disk")

    record_audit_log(
        db=db,
        action="report_downloaded",
        resource_type="report",
        resource_id=report.id,
        user_id=current_user.id
    )

    return FileResponse(
        path=report.file_path,
        filename=os.path.basename(report.file_path),
        media_type="application/pdf"
    )
