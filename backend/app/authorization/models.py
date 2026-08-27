from typing import Optional, Set, Dict, Any
from pydantic import BaseModel, Field
from app.authorization.roles import Role, get_role_permissions, parse_role
from app.authorization.permissions import Permission


class AuthContext(BaseModel):
    user_id: str
    email: Optional[str] = None
    role: Role
    permissions: Set[Permission] = Field(default_factory=set)
    claims: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.permissions:
            self.permissions = get_role_permissions(self.role)

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions


class PolicyContext(BaseModel):
    requester: AuthContext
    action: str
    target_id: Optional[str] = None
    target_role: Optional[Role] = None
    reason: Optional[str] = None
    new_role: Optional[Role] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class PolicyDecision(BaseModel):
    allowed: bool
    policy_name: Optional[str] = None
    reason: Optional[str] = None

    @classmethod
    def allow(cls) -> "PolicyDecision":
        return cls(allowed=True)

    @classmethod
    def deny(cls, policy_name: str, reason: str) -> "PolicyDecision":
        return cls(allowed=False, policy_name=policy_name, reason=reason)
