from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class FingerprintRegisterRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    media_type: str = Field("image", description="image, video_frame, audio")

class FingerprintSearchRequest(BaseModel):
    phash: Optional[str] = None
    sha256_hash: Optional[str] = None
    max_hamming_distance: Optional[int] = Field(10, description="Max hamming distance threshold (0 = exact match)")

class FingerprintMatchResponse(BaseModel):
    id: str
    title: str
    media_type: str
    sha256_hash: str
    phash: Optional[str]
    similarity_score: float
    hamming_distance: int
    match_type: str # exact, approximate
    created_at: datetime

class FingerprintResponse(BaseModel):
    id: str
    user_id: str
    title: str
    media_type: str
    sha256_hash: str
    phash: Optional[str] = None
    dhash: Optional[str] = None
    ahash: Optional[str] = None
    description: Optional[str] = None
    metadata_json: Dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
