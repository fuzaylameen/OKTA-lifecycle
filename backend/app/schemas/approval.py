from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class ApprovalCreateRequest(BaseModel):
    operation_type: str
    requested_by: str
    required_levels: Optional[List[str]] = None
    target_user_id: Optional[str] = None
    target_user_email: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    expires_in_hours: Optional[int] = None


class ApprovalDecisionRequest(BaseModel):
    approver_email: str
    comment: Optional[str] = None


class ApprovalEscalateRequest(BaseModel):
    approver_email: str
    comment: Optional[str] = None
    escalate_to_role: Optional[str] = "SECURITY"
