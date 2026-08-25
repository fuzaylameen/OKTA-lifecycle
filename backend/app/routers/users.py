from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header, Query

from app.schemas.user import UserCreate
from app.schemas.auth import SuspendRequest, RoleAssignRequest
from app.services.user_service import UserService
from app.authorization.permissions import Permission
from app.authorization.roles import Role, parse_role
from app.authorization.models import AuthContext
from app.authorization.dependencies import (
    require_permission,
    evaluate_and_enforce_policy,
)


router = APIRouter(
    prefix="/api/users",
    tags=["Users"]
)

service = UserService()


def _resolve_target_role(role_header: Optional[str] = None, role_query: Optional[str] = None) -> Optional[Role]:
    """Helper to resolve target user role from request context if supplied."""
    candidate = role_header or role_query
    if candidate:
        try:
            return parse_role(candidate)
        except ValueError:
            return None
    return None


@router.get("/")
async def get_users(
    current_user: AuthContext = Depends(require_permission(Permission.USER_LIST))
):
    return await service.list_users()


@router.get("/all")
async def get_all_users(
    current_user: AuthContext = Depends(require_permission(Permission.USER_LIST))
):
    return await service.list_all_users()


@router.get("/deprovisioned")
async def get_deprovisioned_users(
    current_user: AuthContext = Depends(require_permission(Permission.USER_LIST))
):
    return await service.list_deprovisioned_users()


@router.post("/")
async def create_user(
    user: UserCreate,
    current_user: AuthContext = Depends(require_permission(Permission.USER_CREATE))
):
    try:
        result = await service.create_user(
            user.model_dump()
        )

        return {
            "success": True,
            "message": "User created successfully",
            "user": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/{user_id}/provision")
async def provision_user(
    user_id: str,
    current_user: AuthContext = Depends(require_permission(Permission.USER_ACTIVATE))
):
    try:
        result = await service.provision_user(
            user_id
        )

        return {
            "success": True,
            "message": "User provisioning started",
            "result": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    request: SuspendRequest,
    current_user: AuthContext = Depends(require_permission(Permission.USER_SUSPEND)),
    x_target_role: Optional[str] = Header(None, alias="X-Target-Role"),
    target_role: Optional[str] = Query(None)
):
    resolved_target_role = _resolve_target_role(x_target_role, target_role)

    # Enforce contextual policies (e.g. Policy 2, Policy 4, Policy 7)
    evaluate_and_enforce_policy(
        requester=current_user,
        action="suspend",
        target_id=user_id,
        target_role=resolved_target_role,
        reason=request.reason
    )

    try:
        result = await service.suspend_user(
            user_id,
            reason=request.reason
        )

        return {
            "success": True,
            "message": "User suspended successfully",
            "result": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/{user_id}/reactivate")
async def reactivate_user(
    user_id: str,
    current_user: AuthContext = Depends(require_permission(Permission.USER_REACTIVATE)),
    x_target_role: Optional[str] = Header(None, alias="X-Target-Role"),
    target_role: Optional[str] = Query(None)
):
    resolved_target_role = _resolve_target_role(x_target_role, target_role)

    evaluate_and_enforce_policy(
        requester=current_user,
        action="reactivate",
        target_id=user_id,
        target_role=resolved_target_role
    )

    try:
        result = await service.reactivate_user(user_id)

        return {
            "success": True,
            "message": "User reactivated successfully",
            "result": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    current_user: AuthContext = Depends(require_permission(Permission.USER_DEPROVISION)),
    x_target_role: Optional[str] = Header(None, alias="X-Target-Role"),
    target_role: Optional[str] = Query(None)
):
    resolved_target_role = _resolve_target_role(x_target_role, target_role)

    # Enforce Policies (Policy 1: Self-deprovision, Policy 2: Manager->Admin, Policy 3: Manager->Manager/Admin, Policy 7)
    evaluate_and_enforce_policy(
        requester=current_user,
        action="deprovision",
        target_id=user_id,
        target_role=resolved_target_role
    )

    try:
        await service.deactivate_user(
            user_id
        )

        return {
            "success": True,
            "message": "User deactivated"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: AuthContext = Depends(require_permission(Permission.USER_DEPROVISION)),
    x_target_role: Optional[str] = Header(None, alias="X-Target-Role"),
    target_role: Optional[str] = Query(None)
):
    resolved_target_role = _resolve_target_role(x_target_role, target_role)

    # Enforce Policies (Policy 1: Self-deprovision, Policy 2: Manager->Admin, Policy 3: Manager->Manager/Admin, Policy 7)
    evaluate_and_enforce_policy(
        requester=current_user,
        action="deprovision",
        target_id=user_id,
        target_role=resolved_target_role
    )

    try:
        await service.delete_user(
            user_id
        )

        return {
            "success": True,
            "message": "User permanently deleted"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/{user_id}/role")
async def assign_user_role(
    user_id: str,
    request: RoleAssignRequest,
    current_user: AuthContext = Depends(require_permission(Permission.ROLE_MANAGE)),
    x_target_role: Optional[str] = Header(None, alias="X-Target-Role"),
    target_role: Optional[str] = Query(None)
):
    resolved_target_role = _resolve_target_role(x_target_role, target_role)

    try:
        new_role_enum = parse_role(request.role)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    # Enforce Policy 5 (Prevent privilege escalation) and Policy 6 (Prevent self-role escalation)
    evaluate_and_enforce_policy(
        requester=current_user,
        action="role_manage",
        target_id=user_id,
        target_role=resolved_target_role,
        new_role=new_role_enum
    )

    return {
        "success": True,
        "message": f"Role '{new_role_enum.value}' assigned to user {user_id} successfully",
        "user_id": user_id,
        "new_role": new_role_enum.value
    }


# ============================================================
# PASSWORD EXPIRY ENDPOINTS
# ============================================================

@router.get("/password-expiry")
async def get_password_expiry(
    current_user: AuthContext = Depends(require_permission(Permission.USER_READ))
):
    """
    Get password expiry information for all users.
    """
    try:
        return await service.list_password_expiry()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.get("/{user_id}/password-expiry")
async def get_user_password_expiry(
    user_id: str,
    current_user: AuthContext = Depends(require_permission(Permission.USER_READ))
):
    """
    Get password expiry information for one user.
    """
    try:
        return await service.get_password_expiry(
            user_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/{user_id}/expire-password")
async def expire_user_password(
    user_id: str,
    current_user: AuthContext = Depends(require_permission(Permission.USER_UPDATE))
):
    """
    Force a user's password to expire in Okta.
    """
    try:
        result = await service.expire_password(
            user_id
        )

        return {
            "success": True,
            "message": (
                "Password expired successfully. "
                "The user must change their password "
                "at the next login."
            ),
            "result": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )