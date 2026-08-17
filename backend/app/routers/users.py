from fastapi import APIRouter, HTTPException

from app.schemas.user import UserCreate
from app.services.user_service import UserService


router = APIRouter(
    prefix="/api/users",
    tags=["Users"]
)

service = UserService()


@router.get("/")
async def get_users():

    return await service.list_users()


@router.post("/")
async def create_user(user: UserCreate):

    try:

        result = await service.create_user(
            user.model_dump()
        )

        return {
            "success": True,
            "message": "User created successfully",
            "user": result
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/{user_id}/provision")
async def provision_user(user_id: str):

    try:

        result = await service.provision_user(
            user_id
        )

        return {
            "success": True,
            "message": "User provisioning started",
            "result": result
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/{user_id}/deactivate")
async def deactivate_user(user_id: str):

    try:

        await service.deactivate_user(
            user_id
        )

        return {
            "success": True,
            "message": "User deactivated"
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.delete("/{user_id}")
async def delete_user(user_id: str):

    try:

        await service.delete_user(
            user_id
        )

        return {
            "success": True,
            "message": "User permanently deleted"
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )