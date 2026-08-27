from typing import List, Optional
from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.authorization.permissions import Permission
from app.authorization.roles import Role
from app.authorization.models import AuthContext, PolicyContext, PolicyDecision
from app.authorization.engine import policy_engine
from app.audit.authz_logger import log_authz_decision


def require_permission(permission: Permission):
    """
    FastAPI dependency enforcing RBAC permission check.
    Rejects unauthorized requests with 403 Forbidden before reaching service logic.
    """
    async def permission_checker(
        requester: AuthContext = Depends(get_current_user)
    ) -> AuthContext:
        if not requester.has_permission(permission):
            log_authz_decision(
                requester_id=requester.user_id,
                requester_role=requester.role.value,
                action=permission.value,
                decision="DENIED",
                reason=f"Missing required permission: '{permission.value}'"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Missing required permission '{permission.value}'"
            )
        return requester

    return permission_checker


def require_role(allowed_roles: List[Role]):
    """
    FastAPI dependency enforcing high-level Role check.
    """
    async def role_checker(
        requester: AuthContext = Depends(get_current_user)
    ) -> AuthContext:
        if requester.role not in allowed_roles:
            log_authz_decision(
                requester_id=requester.user_id,
                requester_role=requester.role.value,
                action="role_check",
                decision="DENIED",
                reason=f"Role '{requester.role.value}' not in allowed roles: {[r.value for r in allowed_roles]}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient role privilege"
            )
        return requester

    return role_checker


def evaluate_and_enforce_policy(
    requester: AuthContext,
    action: str,
    target_id: Optional[str] = None,
    target_role: Optional[Role] = None,
    reason: Optional[str] = None,
    new_role: Optional[Role] = None,
    **attributes
) -> PolicyDecision:
    """
    Evaluates all registered contextual policies.
    If denied, logs the decision and raises HTTP 403 Forbidden.
    If allowed, logs sensitive operations and returns the decision.
    """
    context = PolicyContext(
        requester=requester,
        action=action,
        target_id=target_id,
        target_role=target_role,
        reason=reason,
        new_role=new_role,
        attributes=attributes,
    )

    decision = policy_engine.evaluate(context)

    if not decision.allowed:
        log_authz_decision(
            requester_id=requester.user_id,
            requester_role=requester.role.value,
            action=action,
            decision="DENIED",
            target_id=target_id,
            policy_name=decision.policy_name,
            reason=decision.reason,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Policy violation ({decision.policy_name}): {decision.reason}"
        )

    # Log allowed sensitive operations
    if action in {"suspend", "deprovision", "delete", "deactivate", "role_manage", "assign_role"}:
        log_authz_decision(
            requester_id=requester.user_id,
            requester_role=requester.role.value,
            action=action,
            decision="ALLOWED",
            target_id=target_id,
            reason=reason,
        )

    return decision
