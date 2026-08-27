from typing import Optional, Dict
from fastapi import APIRouter, HTTPException, Depends, Header, Query

from app.schemas.user import UserCreate
from app.schemas.auth import SuspendRequest, RoleAssignRequest
from app.services.user_service import UserService
from app.services.group_service import GroupService
from app.authorization.permissions import Permission
from app.authorization.roles import Role, parse_role, OKTA_GROUP_ROLE_MAP
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
group_service = GroupService()

ROLE_DEFAULT_OKTA_GROUP: Dict[Role, str] = {
    Role.ADMIN: "Identity-Admins",
    Role.ROLE_MANAGER: "Identity-Role-Managers",
    Role.MANAGER: "Identity-Managers",
    Role.AUDITOR: "Identity-Auditors",
}


async def _sync_user_role_to_okta(user_id: str, new_role: Role) -> dict:
    """
    Sync user's role directly to Okta by:
    1. Finding the matching Okta Identity group for new_role.
    2. Removing the user from any previous Okta Identity groups (SoD enforcement).
    3. Adding the user to the target Okta group.
    """
    all_groups = await group_service.list_groups()
    if not isinstance(all_groups, list):
        all_groups = []

    target_group_id = None
    target_group_name = ROLE_DEFAULT_OKTA_GROUP.get(new_role, "Identity-Admins")

    # 1. Search for matching Okta group in live Okta directory
    for g in all_groups:
        if isinstance(g, dict):
            name = (g.get("profile", {}).get("name") or g.get("name", "")).strip().lower()
            if OKTA_GROUP_ROLE_MAP.get(name) == new_role:
                target_group_id = g.get("id")
                target_group_name = g.get("profile", {}).get("name") or g.get("name")
                break

    # If groups couldn't be listed or not found by map, search by exact target group name
    if not target_group_id:
        for g in all_groups:
            if isinstance(g, dict):
                name = (g.get("profile", {}).get("name") or g.get("name", "")).strip()
                if name.lower() == target_group_name.lower():
                    target_group_id = g.get("id")
                    break

    # 2. Remove user from existing Identity groups (Separation of Duties)
    try:
        user_groups = await service.get_user_groups(user_id)
        if isinstance(user_groups, list):
            for ug in user_groups:
                if isinstance(ug, dict):
                    ug_id = ug.get("id")
                    ug_name = (ug.get("profile", {}).get("name") or ug.get("name", "")).strip().lower()
                    if ug_name in OKTA_GROUP_ROLE_MAP and ug_id and ug_id != target_group_id:
                        await group_service.remove_user(ug_id, user_id)
    except Exception:
        pass

    # 3. Add user to the new Okta group
    if target_group_id:
        await group_service.add_user(target_group_id, user_id)

    return {
        "group_id": target_group_id,
        "group_name": target_group_name
    }


async def _resolve_target_role(user_id: str) -> Optional[Role]:
    """Auto-resolve target user's role from their Okta group membership using user_id."""
    try:
        groups = await service.get_user_groups(user_id)
        group_names = []
        if isinstance(groups, list):
            for g in groups:
                p = g.get("profile", {})
                name = p.get("name") or g.get("name")
                if name:
                    group_names.append(name)
        for group_name in group_names:
            try:
                return parse_role(group_name)
            except ValueError:
                continue
        return None
    except Exception:
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
):
    # Auto-resolve target user's role directly from their Okta group membership
    resolved_target_role = await _resolve_target_role(user_id)

    # Enforce contextual policies (e.g. Policy 2: Manager cannot suspend Admin, Policy 4: Reason check, Policy 7)
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
):
    resolved_target_role = await _resolve_target_role(user_id)

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
):
    resolved_target_role = await _resolve_target_role(user_id)

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
):
    resolved_target_role = await _resolve_target_role(user_id)

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
):
    resolved_target_role = await _resolve_target_role(user_id)

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

    try:
        sync_result = await _sync_user_role_to_okta(user_id, new_role_enum)

        service._create_log(
            action="ASSIGN_ROLE",
            user_id=user_id,
            old_value=resolved_target_role.value if resolved_target_role else None,
            new_value=new_role_enum.value,
            status="SUCCESS",
            message=f"Role '{new_role_enum.value}' assigned in Okta group '{sync_result.get('group_name')}'"
        )

        return {
            "success": True,
            "message": f"Role '{new_role_enum.value}' assigned to user {user_id} successfully",
            "user_id": user_id,
            "new_role": new_role_enum.value,
            "okta_group": sync_result.get("group_name")
        }

    except HTTPException:
        raise
    except Exception as e:
        service._create_log(
            action="ASSIGN_ROLE",
            user_id=user_id,
            old_value=resolved_target_role.value if resolved_target_role else None,
            new_value=new_role_enum.value,
            status="FAILED",
            message=str(e)
        )
        raise HTTPException(
            status_code=400,
            detail=f"Failed to synchronize role assignment with Okta: {str(e)}"
        )



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