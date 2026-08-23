from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models_lifecycle import LifecycleOperation
from app.schemas.approval import (
    ApprovalCreateRequest,
    ApprovalDecisionRequest,
    ApprovalEscalateRequest
)
from app.services import approval_service, lifecycle_execution_service


router = APIRouter(
    prefix="/api/approvals",
    tags=["Approvals"]
)


def _serialize(approval):

    return {
        "id": approval.id,
        "operation_type": approval.operation_type,
        "target_user_id": approval.target_user_id,
        "target_user_email": approval.target_user_email,
        "requested_by": approval.requested_by,
        "status": approval.status,
        "current_level": approval.current_level,
        "risk_score": approval.risk_score,
        "risk_band": approval.risk_band,
        "policy_source": approval.policy_source,
        "created_at": approval.created_at,
        "updated_at": approval.updated_at,
        "expires_at": approval.expires_at
    }


async def _finalize_linked_operation(db: Session, approval_id: int):
    """
    If this approval request is driving a Category 7 lifecycle
    operation, ask lifecycle_execution_service (the sole owner of the
    execution transition) to react to the latest decision.
    """

    operation = (
        db.query(LifecycleOperation)
        .filter(LifecycleOperation.approval_request_id == approval_id)
        .first()
    )

    if operation:
        await lifecycle_execution_service.finalize_operation(db, operation.id)


@router.post("/")
async def create_approval(
    request: ApprovalCreateRequest,
    db: Session = Depends(get_db)
):

    try:

        approval = approval_service.create_approval_request(
            db,
            operation_type=request.operation_type,
            requested_by=request.requested_by,
            required_levels=request.required_levels,
            target_user_id=request.target_user_id,
            target_user_email=request.target_user_email,
            payload=request.payload,
            expires_in_hours=request.expires_in_hours
        )

        return {
            "success": True,
            "approval": _serialize(approval)
        }

    except Exception as e:

        raise HTTPException(status_code=400, detail=str(e))


@router.get("/")
def get_queue(
    status: str = None,
    approver_role: str = None,
    db: Session = Depends(get_db)
):

    approvals = approval_service.list_queue(db, status=status, approver_role=approver_role)

    return [_serialize(a) for a in approvals]


@router.get("/{approval_id}")
def get_approval(
    approval_id: int,
    db: Session = Depends(get_db)
):

    try:
        approval = approval_service.get_approval(db, approval_id)
        return _serialize(approval)

    except approval_service.ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{approval_id}/history")
def get_history(
    approval_id: int,
    db: Session = Depends(get_db)
):

    try:

        steps = approval_service.get_history(db, approval_id)

        return [
            {
                "level": step.level,
                "approver_role": step.approver_role,
                "approver_email": step.approver_email,
                "decision": step.decision,
                "comment": step.comment,
                "decided_at": step.decided_at,
                "created_at": step.created_at
            }
            for step in steps
        ]

    except approval_service.ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{approval_id}/approve")
async def approve(
    approval_id: int,
    request: ApprovalDecisionRequest,
    db: Session = Depends(get_db)
):

    try:

        approval = approval_service.decide(
            db,
            approval_id,
            request.approver_email,
            "APPROVED",
            comment=request.comment
        )

        await _finalize_linked_operation(db, approval_id)

        db.refresh(approval)

        return {
            "success": True,
            "approval": _serialize(approval)
        }

    except approval_service.ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except approval_service.SeparationOfDutiesError as e:
        raise HTTPException(status_code=403, detail=str(e))

    except approval_service.InvalidApprovalStateError as e:
        raise HTTPException(status_code=409, detail=str(e))

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{approval_id}/reject")
async def reject(
    approval_id: int,
    request: ApprovalDecisionRequest,
    db: Session = Depends(get_db)
):

    try:

        approval = approval_service.decide(
            db,
            approval_id,
            request.approver_email,
            "REJECTED",
            comment=request.comment
        )

        await _finalize_linked_operation(db, approval_id)

        db.refresh(approval)

        return {
            "success": True,
            "approval": _serialize(approval)
        }

    except approval_service.ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except approval_service.SeparationOfDutiesError as e:
        raise HTTPException(status_code=403, detail=str(e))

    except approval_service.InvalidApprovalStateError as e:
        raise HTTPException(status_code=409, detail=str(e))

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{approval_id}/escalate")
def escalate(
    approval_id: int,
    request: ApprovalEscalateRequest,
    db: Session = Depends(get_db)
):

    try:

        approval = approval_service.escalate(
            db,
            approval_id,
            request.approver_email,
            comment=request.comment,
            escalate_to_role=request.escalate_to_role
        )

        return {
            "success": True,
            "approval": _serialize(approval)
        }

    except approval_service.ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except approval_service.InvalidApprovalStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
