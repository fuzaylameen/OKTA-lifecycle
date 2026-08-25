from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.services.group_service import GroupService
from app.authorization.permissions import Permission
from app.authorization.models import AuthContext
from app.authorization.dependencies import require_permission


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