from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import AuditLog, AuthzAuditLog
from app.authorization.permissions import Permission
from app.authorization.models import AuthContext
from app.authorization.dependencies import require_permission


router = APIRouter(
    prefix="/api/logs",
    tags=["Logs"]
)


@router.get("/")
def get_logs(
    db: Session = Depends(get_db),
    current_user: AuthContext = Depends(require_permission(Permission.AUDIT_READ))
):
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .all()
    )

    return [
        {
            "id": log.id,
            "action": log.action,
            "user_id": log.user_id,
            "user_email": log.user_email,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "status": log.status,
            "message": log.message,
            "created_at": log.created_at
        }
        for log in logs
    ]


@router.get("/authz")
def get_authz_logs(
    db: Session = Depends(get_db),
    current_user: AuthContext = Depends(require_permission(Permission.AUDIT_READ))
):
    """
    Retrieve security authorization audit trail (ALLOW / DENY decisions).
    """
    logs = (
        db.query(AuthzAuditLog)
        .order_by(AuthzAuditLog.created_at.desc())
        .all()
    )

    return [
        {
            "id": log.id,
            "requester_id": log.requester_id,
            "requester_role": log.requester_role,
            "action": log.action,
            "target_id": log.target_id,
            "decision": log.decision,
            "policy_name": log.policy_name,
            "reason": log.reason,
            "created_at": log.created_at
        }
        for log in logs
    ]