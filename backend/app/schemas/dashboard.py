from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime

class ActivityItem(BaseModel):
    id: str
    action: str
    description: str
    timestamp: datetime
    category: str
    severity: str

class RiskDistributionItem(BaseModel):
    name: str
    count: int
    color: str

class CaseStatusItem(BaseModel):
    status: str
    count: int
    label: str

class DashboardStatsResponse(BaseModel):
    total_cases: int
    content_analyzed: int
    high_risk_cases: int
    pending_reports: int
    confirmed_removal_cases: int
    cases_under_review: int
    risk_distribution: List[RiskDistributionItem]
    case_status_distribution: List[CaseStatusItem]
    recent_activities: List[ActivityItem]
    recent_analyses: List[Dict[str, Any]]
