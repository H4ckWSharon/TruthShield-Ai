from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class TextAnalysisRequest(BaseModel):
    text: str = Field(..., min_length=2, max_length=10000)
    case_id: Optional[str] = None
    context_type: Optional[str] = "social_media_post"

class URLAnalysisRequest(BaseModel):
    url: str = Field(..., min_length=4, max_length=2048)
    case_id: Optional[str] = None

class AnalysisFinding(BaseModel):
    category: str
    severity: str
    description: str
    score: float
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None

class AnalysisEvidenceItem(BaseModel):
    indicator: str
    observed_value: Any
    interpretation: str

class AnalysisResponse(BaseModel):
    analysis_id: str
    content_type: str # image, video, audio, text, url
    risk_level: str   # low, medium, high, critical
    confidence: float
    findings: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    explanation: str
    limitations: List[str]
    recommended_action: str
    input_reference: Optional[str] = None
    raw_metadata: Optional[Dict[str, Any]] = None
    case_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
