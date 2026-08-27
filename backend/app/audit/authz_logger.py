import logging
from typing import Optional
from app.db.database import SessionLocal
from app.db.models import AuthzAuditLog

logger = logging.getLogger("intelliid.authz")


def log_authz_decision(
    requester_id: str,
    requester_role: str,
    action: str,
    decision: str,
    target_id: Optional[str] = None,
    policy_name: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """
    Persist an authorization decision (ALLOW or DENY) to the database audit log.
    Ensures zero exposure of secrets or private keys.
    """
    # Also log to structured application logger for real-time monitoring
    log_msg = (
        f"AUTHZ DECISION: [{decision}] requester={requester_id} role={requester_role} "
        f"action={action} target={target_id} policy={policy_name} reason={reason}"
    )
    if decision == "DENIED":
        logger.warning(log_msg)
    else:
        logger.info(log_msg)

    # Persist to database
    db = SessionLocal()
    try:
        entry = AuthzAuditLog(
            requester_id=str(requester_id),
            requester_role=str(requester_role),
            action=action,
            target_id=str(target_id) if target_id else None,
            decision=decision,
            policy_name=policy_name,
            reason=reason,
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to persist authorization audit log: {e}")
        db.rollback()
    finally:
        db.close()
