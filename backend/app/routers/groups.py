from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.services.group_service import GroupService
from app.authorization.permissions import Permission
from app.authorization.models import AuthContext
from app.authorization.dependencies import require_permission, evaluate_and_enforce_policy


router = APIRouter(
    prefix="/api/groups",
    tags=["Groups"]
)

service = GroupService()


class MoveUserRequest(BaseModel):
    user_id: str
    old_group_id: str
    new_group_id: str


@router.get("/")
async def get_groups(
    current_user: AuthContext = Depends(require_permission(Permission.USER_READ))
):
    return await service.list_groups()


@router.post("/move")
async def move_user(
    request: MoveUserRequest,
    current_user: AuthContext = Depends(require_permission(Permission.USER_UPDATE))
):
    # Resolve group names for policy evaluation
    group_map = {}
    try:
        groups = await service.list_groups()
        if isinstance(groups, list):
            for g in groups:
                gid = g.get("id")
                gname = g.get("profile", {}).get("name")
                if gid and gname:
                    group_map[gid] = gname
    except Exception:
        pass

    old_group_name = group_map.get(request.old_group_id, request.old_group_id)
    new_group_name = group_map.get(request.new_group_id, request.new_group_id)

    # Enforce contextual policy (Policy 8: ProtectedIdentityGroupPolicy)
    evaluate_and_enforce_policy(
        requester=current_user,
        action="group_manage",
        target_id=request.user_id,
        old_group=old_group_name,
        new_group=new_group_name,
        old_group_id=request.old_group_id,
        new_group_id=request.new_group_id,
    )

    try:
        result = await service.move_user(
            request.user_id,
            request.old_group_id,
            request.new_group_id
        )

        return {
            "success": True,
            "message": "User moved successfully",
            "result": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )