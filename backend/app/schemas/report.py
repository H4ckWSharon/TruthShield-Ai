from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class ReportCreate(BaseModel):
    case_id: str
    template_type: str = Field("incident", description="youtube, instagram, facebook, general_web, incident")
    title: Optional[str] = None
    summary: Optional[str] = None

class ReportResponse(BaseModel):
    id: str
    case_id: str
    user_id: str
    template_type: str
    title: str
    summary: str
    findings_snapshot: Dict[str, Any]
    file_path: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
