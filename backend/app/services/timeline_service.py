from app.db.models import AuditLog
from app.db.models_lifecycle import IdentityTimelineEvent, ApprovalStep, ApprovalRequest


# Category 11. This module only ever reads from AuditLog - it never
# writes to it and never alters its schema, so existing audit
# functionality (UserService._create_log, audit_service.create_audit_log)
# is completely unaffected.

AUDIT_ACTION_CATEGORY = {
    "CREATE_USER": "CREATION",
    "PROVISION_USER": "ACTIVATION",
    "DEACTIVATE_USER": "SUSPENSION",
    "BULK_DEACTIVATE_USER": "SUSPENSION",
    "DELETE_USER": "OFFBOARDING"
}


def _from_audit_logs(db, user_id):

    logs = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == str(user_id))
        .all()
    )

    events = []

    for log in logs:

        events.append({
            "source": "AUDIT_LOG",
            "category": AUDIT_ACTION_CATEGORY.get(log.action, "OTHER"),
            "event_type": log.action,
            "description": log.message,
            "actor_email": log.user_email,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "status": log.status,
            "created_at": log.created_at
        })

    return events


def _from_timeline_events(db, user_id):

    rows = (
        db.query(IdentityTimelineEvent)
        .filter(IdentityTimelineEvent.identity_user_id == str(user_id))
        .all()
    )

    events = []

    for row in rows:

        events.append({
            "source": "TIMELINE_EVENT",
            "category": row.event_category,
            "event_type": row.event_type,
            "description": row.description,
            "actor_email": row.actor_email,
            "old_value": row.old_value,
            "new_value": row.new_value,
            "status": None,
            "created_at": row.created_at
        })

    return events


def _from_approval_decisions(db, user_id):

    rows = (
        db.query(ApprovalStep)
        .join(ApprovalRequest, ApprovalStep.approval_request_id == ApprovalRequest.id)
        .filter(ApprovalRequest.target_user_id == str(user_id))
        .filter(ApprovalStep.decision != "PENDING")
        .all()
    )

    events = []

    for step in rows:

        events.append({
            "source": "APPROVAL_STEP",
            "category": "APPROVAL",
            "event_type": f"APPROVAL_LEVEL_{step.level}_{step.decision}",
            "description": (
                f"Level {step.level} ({step.approver_role}) "
                f"{step.decision.lower()}"
            ),
            "actor_email": step.approver_email,
            "old_value": None,
            "new_value": step.decision,
            "status": None,
            "created_at": step.decided_at or step.created_at
        })

    return events


def get_timeline(db, user_id, category=None):

    events = (
        _from_audit_logs(db, user_id)
        + _from_timeline_events(db, user_id)
        + _from_approval_decisions(db, user_id)
    )

    if category:
        events = [e for e in events if e["category"] == category.upper()]

    events.sort(key=lambda e: e["created_at"] or 0)

    return events
