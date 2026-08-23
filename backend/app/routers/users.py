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

@router.get("/all")
async def get_all_users():

    return await service.list_all_users()

@router.get("/deprovisioned")
async def get_deprovisioned_users():

    return await service.list_deprovisioned_users()


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


# ============================================================
# PASSWORD EXPIRY ENDPOINTS
# ============================================================

@router.get("/password-expiry")
async def get_password_expiry():

    """
    Get password expiry information for all users.
    """

    try:

        return await service.list_password_expiry()

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.get("/{user_id}/password-expiry")
async def get_user_password_expiry(user_id: str):

    """
    Get password expiry information for one user.
    """

    try:

        return await service.get_password_expiry(
            user_id
        )

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.post("/{user_id}/expire-password")
async def expire_user_password(user_id: str):

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

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )