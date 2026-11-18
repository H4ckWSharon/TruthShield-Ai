from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class RemovalWorkflowCreate(BaseModel):
    case_id: str
    platform: str = Field(..., description="youtube, instagram, facebook, reddit, general_web")
    violation_type: str = Field(..., description="ncii, impersonation, copyright, harassment, defamation")
    report_content: Optional[str] = None
    notes: Optional[str] = None

class RemovalApprovalRequest(BaseModel):
    workflow_id: str
    approved: bool
    notes: Optional[str] = None
    submission_reference: Optional[str] = None

class RemovalWorkflowResponse(BaseModel):
    id: str
    case_id: str
    user_id: str
    platform: str
    violation_type: str
    report_content: str
    status: str
    human_approved: bool
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    submission_reference: Optional[str] = None
    notes: Optional[str] = None
    official_portal_url: Optional[str] = None
    guidance_steps: Optional[List[str]] = None
    updated_at: datetime

    model_config = {"from_attributes": True}
