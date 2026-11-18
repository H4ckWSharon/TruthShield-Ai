from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CaseCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    category: str = Field(..., description="ncii, deepfake, impersonation, harassment, threats, misinformation, phishing, other")
    description: Optional[str] = None
    risk_level: Optional[str] = Field("medium", description="low, medium, high, critical")
    urls: Optional[List[str]] = Field(default_factory=list)
    notes: Optional[str] = None

class CaseUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    risk_level: Optional[str] = None
    status: Optional[str] = None
    urls: Optional[List[str]] = None
    notes: Optional[str] = None

class CaseResponse(BaseModel):
    id: str
    case_number: str
    title: str
    category: str
    description: Optional[str] = None
    user_id: str
    risk_level: str
    status: str
    urls: List[str]
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    evidence_count: Optional[int] = 0

    model_config = {"from_attributes": True}

class CaseListResponse(BaseModel):
    items: List[CaseResponse]
    total: int
