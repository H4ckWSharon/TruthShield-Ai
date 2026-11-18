from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class EvidenceResponse(BaseModel):
    id: str
    case_id: Optional[str] = None
    user_id: str
    original_filename: str
    file_size: int
    mime_type: str
    sha256_hash: str
    evidence_type: str
    description: Optional[str] = None
    is_sensitive: bool
    metadata_json: Dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}

class EvidenceMetadata(BaseModel):
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    duration: Optional[float] = None
    perceptual_hashes: Optional[Dict[str, str]] = None
    exif: Optional[Dict[str, Any]] = None
