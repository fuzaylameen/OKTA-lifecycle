from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.group_service import GroupService


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
async def get_groups():

    return await service.list_groups()


@router.post("/move")
async def move_user(request: MoveUserRequest):

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

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )