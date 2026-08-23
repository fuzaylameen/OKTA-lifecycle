from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import json

from app.db.database import get_db
from app.schemas.lifecycle import DryRunRequest
from app.services import lifecycle_execution_service


router = APIRouter(
    prefix="/api/lifecycle",
    tags=["Lifecycle Execution"]
)


def _serialize(operation):

    return {
        "id": operation.id,
        "approval_request_id": operation.approval_request_id,
        "operation_type": operation.operation_type,
        "target_user_id": operation.target_user_id,
        "target_user_email": operation.target_user_email,
        "requested_by": operation.requested_by,
        "status": operation.status,
        "preview": (
            json.loads(operation.preview_payload)
            if operation.preview_payload else None
        ),
        "executed_result": (
            json.loads(operation.executed_payload)
            if operation.executed_payload else None
        ),
        "verification_result": (
            json.loads(operation.verification_result)
            if operation.verification_result else None
        ),
        "created_at": operation.created_at,
        "updated_at": operation.updated_at,
        "executed_at": operation.executed_at
    }


@router.post("/dry-run")
async def dry_run(
    request: DryRunRequest,
    db: Session = Depends(get_db)
):

    try:

        operation = await lifecycle_execution_service.dry_run(
            db,
            operation_type=request.operation_type,
            requested_by=request.requested_by,
            target_user_id=request.target_user_id,
            target_user_email=request.target_user_email,
            payload=request.payload
        )

        return {
            "success": True,
            "operation": _serialize(operation)
        }

    except lifecycle_execution_service.LifecycleOperationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{operation_id}")
def get_operation(
    operation_id: int,
    db: Session = Depends(get_db)
):

    try:
        operation = lifecycle_execution_service.get_operation(db, operation_id)
        return _serialize(operation)

    except lifecycle_execution_service.LifecycleOperationError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{operation_id}/confirm")
async def confirm(
    operation_id: int,
    db: Session = Depends(get_db)
):

    try:

        operation = await lifecycle_execution_service.confirm(db, operation_id)

        return {
            "success": True,
            "operation": _serialize(operation)
        }

    except lifecycle_execution_service.LifecycleOperationError as e:
        raise HTTPException(status_code=409, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{operation_id}/cancel")
async def cancel(
    operation_id: int,
    db: Session = Depends(get_db)
):

    try:

        operation = await lifecycle_execution_service.cancel(db, operation_id)

        return {
            "success": True,
            "operation": _serialize(operation)
        }

    except lifecycle_execution_service.LifecycleOperationError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{operation_id}/verify")
async def verify(
    operation_id: int,
    db: Session = Depends(get_db)
):

    try:

        operation = await lifecycle_execution_service.verify(db, operation_id)

        return {
            "success": True,
            "operation": _serialize(operation)
        }

    except lifecycle_execution_service.LifecycleOperationError as e:
        raise HTTPException(status_code=409, detail=str(e))
