from fastapi import APIRouter, HTTPException, UploadFile, File, Depends

from app.schemas.bulk_user import BulkUserRequest
from app.services.bulk_user_service import BulkUserService
from app.authorization.permissions import Permission
from app.authorization.models import AuthContext
from app.authorization.dependencies import require_permission, evaluate_and_enforce_policy


router = APIRouter(
    prefix="/api/bulk/users",
    tags=["Bulk Users"]
)

service = BulkUserService()


@router.post("/provision")
async def bulk_provision(
    request: BulkUserRequest,
    current_user: AuthContext = Depends(require_permission(Permission.USER_ACTIVATE))
):
    try:
        return await service.bulk_provision(
            request.user_ids
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/deactivate")
async def bulk_deactivate(
    request: BulkUserRequest,
    current_user: AuthContext = Depends(require_permission(Permission.USER_DEPROVISION))
):
    # Enforce Policy 1: Self-deprovisioning prevention on each item in the bulk list
    for uid in request.user_ids:
        evaluate_and_enforce_policy(
            requester=current_user,
            action="deprovision",
            target_id=uid
        )

    try:
        return await service.bulk_deactivate(
            request.user_ids
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.delete("/")
async def bulk_delete(
    request: BulkUserRequest,
    current_user: AuthContext = Depends(require_permission(Permission.USER_DEPROVISION))
):
    # Enforce Policy 1: Self-deprovisioning prevention on each item in the bulk list
    for uid in request.user_ids:
        evaluate_and_enforce_policy(
            requester=current_user,
            action="deprovision",
            target_id=uid
        )

    try:
        return await service.bulk_delete(
            request.user_ids
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/import-csv")
async def import_users_csv(
    file: UploadFile = File(...),
    current_user: AuthContext = Depends(require_permission(Permission.USER_CREATE))
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported"
        )

    try:
        return await service.import_users_from_csv(file)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )