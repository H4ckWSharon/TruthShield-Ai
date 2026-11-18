from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class NotificationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    message: str
    notification_type: str
    is_read: bool
    case_id: Optional[str] = None
    link: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class NotificationUpdate(BaseModel):
    is_read: bool
