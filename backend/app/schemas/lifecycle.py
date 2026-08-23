from pydantic import BaseModel
from typing import Optional, Dict, Any


class DryRunRequest(BaseModel):
    operation_type: str
    requested_by: str
    target_user_id: Optional[str] = None
    target_user_email: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
