from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.entities import User, Case, AnalysisResult, Report, RemovalWorkflow, AuditLog, CaseStatus, RiskLevel
from app.schemas.dashboard import DashboardStatsResponse, ActivityItem, RiskDistributionItem, CaseStatusItem

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/stats", response_model=DashboardStatsResponse)
def get_dashboard_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve real-time database-driven metrics and charts.
    All data is computed directly from live database tables.
    """
    is_admin = current_user.role in ("admin", "analyst")
    
    # Filter cases by user unless user has admin/analyst privileges
    case_query = db.query(Case)
    analysis_query = db.query(AnalysisResult)
    report_query = db.query(Report)
    removal_query = db.query(RemovalWorkflow)

    if not is_admin:
        case_query = case_query.filter(Case.user_id == current_user.id)
        analysis_query = analysis_query.filter(AnalysisResult.user_id == current_user.id)
        report_query = report_query.filter(Report.user_id == current_user.id)
        removal_query = removal_query.filter(RemovalWorkflow.user_id == current_user.id)

    total_cases = case_query.count()
    content_analyzed = analysis_query.count()
    
    high_risk_cases = case_query.filter(Case.risk_level.in_([RiskLevel.HIGH.value, RiskLevel.CRITICAL.value])).count()
    pending_reports = report_query.filter(Report.status.in_(["draft", "generated"])).count()
    confirmed_removal_cases = case_query.filter(Case.status == CaseStatus.CONFIRMED_REMOVED.value).count()
    cases_under_review = case_query.filter(Case.status.in_([CaseStatus.UNDER_REVIEW.value, CaseStatus.PENDING_VERIFICATION.value])).count()

    # Risk Distribution Chart Data
    risk_colors = {
        "critical": "#EF4444",
        "high": "#F97316",
        "medium": "#F59E0B",
        "low": "#10B981"
    }
    risk_counts = (
        case_query.with_entities(Case.risk_level, func.count(Case.id))
        .group_by(Case.risk_level)
        .all()
    )
    risk_map = {r.value: 0 for r in RiskLevel}
    for r_level, count in risk_counts:
        risk_map[r_level] = count

    risk_distribution = [
        RiskDistributionItem(
            name=lvl.capitalize(),
            count=risk_map[lvl],
            color=risk_colors.get(lvl, "#6B7280")
        )
        for lvl in ["critical", "high", "medium", "low"]
    ]

    # Case Status Distribution
    status_counts = (
        case_query.with_entities(Case.status, func.count(Case.id))
        .group_by(Case.status)
        .all()
    )
    status_map = {s.value: 0 for s in CaseStatus}
    for s_val, count in status_counts:
        status_map[s_val] = count

    case_status_distribution = [
        CaseStatusItem(
            status=s_val,
            count=status_map[s_val],
            label=s_val.replace("_", " ").title()
        )
        for s_val in [
            CaseStatus.DETECTED.value,
            CaseStatus.PENDING_VERIFICATION.value,
            CaseStatus.VERIFIED.value,
            CaseStatus.REPORT_PREPARED.value,
            CaseStatus.SUBMITTED.value,
            CaseStatus.UNDER_REVIEW.value,
            CaseStatus.CONFIRMED_REMOVED.value,
            CaseStatus.REJECTED.value,
            CaseStatus.UNRESOLVED.value
        ]
    ]

    # Recent Activities (from AuditLog)
    audit_query = db.query(AuditLog)
    if not is_admin:
        audit_query = audit_query.filter(AuditLog.user_id == current_user.id)
    recent_logs = audit_query.order_by(AuditLog.timestamp.desc()).limit(8).all()

    recent_activities = []
    for log in recent_logs:
        action_clean = log.action.replace("_", " ").title()
        details_str = f"Resource: {log.resource_type.upper()}"
        if log.resource_id:
            details_str += f" ({log.resource_id[:8]})"
            
        severity = "high" if "delete" in log.action or "critical" in log.action else "normal"
        
        recent_activities.append(
            ActivityItem(
                id=log.id,
                action=action_clean,
                description=details_str,
                timestamp=log.timestamp,
                category=log.resource_type,
                severity=severity
            )
        )

    # Recent Analyses
    recent_analysis_records = (
        analysis_query.order_by(AnalysisResult.created_at.desc())
        .limit(6)
        .all()
    )
    recent_analyses = [
        {
            "id": a.id,
            "content_type": a.content_type,
            "risk_level": a.risk_level,
            "confidence": a.confidence,
            "input_reference": a.input_reference,
            "created_at": a.created_at.isoformat()
        }
        for a in recent_analysis_records
    ]

    return DashboardStatsResponse(
        total_cases=total_cases,
        content_analyzed=content_analyzed,
        high_risk_cases=high_risk_cases,
        pending_reports=pending_reports,
        confirmed_removal_cases=confirmed_removal_cases,
        cases_under_review=cases_under_review,
        risk_distribution=risk_distribution,
        case_status_distribution=case_status_distribution,
        recent_activities=recent_activities,
        recent_analyses=recent_analyses
    )
