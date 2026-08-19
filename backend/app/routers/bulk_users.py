from fastapi import APIRouter, HTTPException

from app.schemas.bulk_user import BulkUserRequest
from app.services.bulk_user_service import BulkUserService


router = APIRouter(
    prefix="/api/bulk/users",
    tags=["Bulk Users"]
)

service = BulkUserService()


@router.post("/provision")
async def bulk_provision(request: BulkUserRequest):

    try:
        return await service.bulk_provision(
            request.user_ids
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/deactivate")
async def bulk_deactivate(request: BulkUserRequest):

    try:
        return await service.bulk_deactivate(
            request.user_ids
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.delete("/")
async def bulk_delete(request: BulkUserRequest):

    try:
        return await service.bulk_delete(
            request.user_ids
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )