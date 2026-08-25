from typing import Optional, List
from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    email: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


class TokenRequest(BaseModel):
    user_id: str = Field(..., description="Unique User/Requester ID")
    email: str = Field(..., description="User email address")
    role: str = Field(..., description="Viewer, Operator, Manager, or Admin")


class SuspendRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Non-empty reason for account suspension")


class RoleAssignRequest(BaseModel):
    role: str = Field(..., description="Target role to assign (Viewer, Operator, Manager, Admin)")
