from app.db.models import AuditLog


def create_audit_log(
    db,
    action,
    user_id=None,
    user_email=None,
    old_value=None,
    new_value=None,
    status="SUCCESS",
    message=None
):

    log = AuditLog(
        action=action,
        user_id=user_id,
        user_email=user_email,
        old_value=old_value,
        new_value=new_value,
        status=status,
        message=message
    )

    db.add(log)
    db.commit()

    return log