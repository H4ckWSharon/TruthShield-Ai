from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SystemHealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    company: str
    environment: str
    database_status: str
    ollama_status: str
    redis_status: str
    storage_accessible: bool
    active_cases: int
    total_users: int
    system_time: datetime

class UserAdminView(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    case_count: int

    model_config = {"from_attributes": True}

class UserRoleUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None

class AIModelConfigItem(BaseModel):
    id: str
    model_name: str
    provider: str
    is_active: bool
    endpoint_url: Optional[str] = None
    description: Optional[str] = None
    updated_at: datetime

    model_config = {"from_attributes": True}

class AIModelToggleRequest(BaseModel):
    is_active: bool
    endpoint_url: Optional[str] = None
