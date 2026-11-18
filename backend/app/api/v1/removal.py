import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.deps import get_current_user, record_audit_log
from app.models.entities import User, Case, RemovalWorkflow, Notification
from app.schemas.removal import (
    RemovalWorkflowCreate, RemovalApprovalRequest, RemovalWorkflowResponse
)
from app.services.removal.workflow_engine import prepare_removal_dossier, resolve_platform_guidance
from app.services.media.url_analyzer import verify_url_live_status, SSRFSecurityViolation

router = APIRouter(prefix="/removal", tags=["Removal Assistance Workflow"])

@router.post("/prepare-report", response_model=RemovalWorkflowResponse, status_code=status.HTTP_201_CREATED)
def prepare_report(
    payload: RemovalWorkflowCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Prepare a platform-specific violation report package requiring human approval."""
    case = db.query(Case).filter(Case.id == payload.case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if current_user.role not in ("admin", "analyst") and case.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    case_dict = {
        "case_number": case.case_number,
        "description": case.description,
        "urls": case.urls or []
    }

    dossier = prepare_removal_dossier(
        case_data=case_dict,
        platform=payload.platform,
        violation_type=payload.violation_type
    )

    workflow = RemovalWorkflow(
        id=str(uuid.uuid4()),
        case_id=case.id,
        user_id=current_user.id,
        platform=payload.platform,
        violation_type=payload.violation_type,
        report_content=payload.report_content or dossier["report_content"],
        status="pending_review",
        human_approved=False,
        notes=payload.notes,
        updated_at=datetime.now(timezone.utc)
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    record_audit_log(
        db=db,
        action="removal_dossier_prepared",
        resource_type="removal_workflow",
        resource_id=workflow.id,
        user_id=current_user.id,
        details={"platform": payload.platform, "violation": payload.violation_type}
    )

    workflow_resp = RemovalWorkflowResponse.model_validate(workflow)
    workflow_resp.official_portal_url = dossier["official_portal_url"]
    workflow_resp.guidance_steps = dossier["guidance_steps"]
    return workflow_resp

@router.post("/approve", response_model=RemovalWorkflowResponse)
def approve_and_record_submission(
    payload: RemovalApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Investigator gate: Human approval of the prepared removal dossier
    and recording official submission details.
    """
    workflow = db.query(RemovalWorkflow).filter(RemovalWorkflow.id == payload.workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Removal workflow not found")

    if current_user.role not in ("admin", "analyst") and workflow.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    case = db.query(Case).filter(Case.id == workflow.case_id).first()

    if payload.approved:
        workflow.human_approved = True
        workflow.approved_by = current_user.id
        workflow.approved_at = datetime.now(timezone.utc)
        workflow.status = "submitted"
        if payload.submission_reference:
            workflow.submission_reference = payload.submission_reference
        if payload.notes:
            workflow.notes = payload.notes

        if case:
            case.status = "submitted"
            case.updated_at = datetime.now(timezone.utc)

        notif = Notification(
            id=str(uuid.uuid4()),
            user_id=workflow.user_id,
            title="Removal Dossier Approved & Submitted",
            message=f"Report for {workflow.platform.upper()} has been approved. Tracking reference: {payload.submission_reference or 'Pending confirmation'}.",
            notification_type="removal_update",
            case_id=workflow.case_id
        )
        db.add(notif)
    else:
        workflow.human_approved = False
        workflow.status = "rejected"
        if payload.notes:
            workflow.notes = payload.notes

    workflow.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(workflow)

    record_audit_log(
        db=db,
        action="removal_approved" if payload.approved else "removal_rejected",
        resource_type="removal_workflow",
        resource_id=workflow.id,
        user_id=current_user.id,
        details={"approved": payload.approved, "reference": payload.submission_reference}
    )

    guidance = resolve_platform_guidance(workflow.platform, workflow.violation_type)
    resp = RemovalWorkflowResponse.model_validate(workflow)
    resp.official_portal_url = guidance["url"]
    resp.guidance_steps = guidance["steps"]
    return resp

@router.post("/verify-url/{case_id}")
async def verify_case_urls(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Re-check accessible target URLs for a case using SSRF-safe live probing.
    Only marks case as CONFIRMED_REMOVED when removal is actually verified.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if current_user.role not in ("admin", "analyst") and case.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    urls = case.urls or []
    if not urls:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case has no target URLs to verify")

    results: List[Dict[str, Any]] = []
    for target_url in urls:
        try:
            check = await verify_url_live_status(target_url)
            results.append(check)
        except SSRFSecurityViolation as exc:
            results.append({
                "url": target_url,
                "http_status": None,
                "verification_status": "ssrf_blocked",
                "confirmed_removed": False,
                "detail": str(exc),
            })

    all_confirmed_removed = len(results) > 0 and all(r.get("confirmed_removed") for r in results)

    if all_confirmed_removed and case.status != "confirmed_removed":
        case.status = "confirmed_removed"
        case.updated_at = datetime.now(timezone.utc)
        db.add(Notification(
            id=str(uuid.uuid4()),
            user_id=case.user_id,
            title=f"Verified Removal: {case.case_number}",
            message="All target URLs verified as removed/unavailable (HTTP 404/410).",
            notification_type="removal_update",
            case_id=case.id
        ))
        db.commit()

    record_audit_log(
        db=db,
        action="removal_url_recheck",
        resource_type="case",
        resource_id=case.id,
        user_id=current_user.id,
        details={"urls_checked": len(results), "confirmed_removed": all_confirmed_removed}
    )

    return {
        "case_id": case.id,
        "case_number": case.case_number,
        "case_status": case.status,
        "all_confirmed_removed": all_confirmed_removed,
        "results": results,
    }

@router.get("/status/{case_id}", response_model=List[RemovalWorkflowResponse])
def get_case_removal_workflows(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all removal assistance workflows associated with a case."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if current_user.role not in ("admin", "analyst") and case.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    workflows = (
        db.query(RemovalWorkflow)
        .filter(RemovalWorkflow.case_id == case_id)
        .order_by(RemovalWorkflow.updated_at.desc())
        .all()
    )
    results = []
    for w in workflows:
        guidance = resolve_platform_guidance(w.platform, w.violation_type)
        r = RemovalWorkflowResponse.model_validate(w)
        r.official_portal_url = guidance["url"]
        r.guidance_steps = guidance["steps"]
        results.append(r)
    return results
