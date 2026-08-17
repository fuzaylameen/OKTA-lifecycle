from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import AuditLog


router = APIRouter(
    prefix="/api/logs",
    tags=["Logs"]
)


@router.get("/")
def get_logs(
    db: Session = Depends(get_db)
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