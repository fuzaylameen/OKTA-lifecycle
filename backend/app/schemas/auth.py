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
    email: str = Field(..., description="User email address registered in Okta directory")


class SuspendRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Non-empty reason for account suspension")


class RoleAssignRequest(BaseModel):
    role: str = Field(..., description="Target role to assign (Auditor, Manager, Admin, RoleManager)")

