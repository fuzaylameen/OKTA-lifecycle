from app.db.models_lifecycle import IdentityTimelineEvent


def backfill_identity(
    db,
    target_user_id,
    target_user_email=None,
    related_approval_id=None,
    related_operation_id=None
):
    """
    Updates identity_user_id/identity_email on previously recorded
    timeline events that did not yet know the identity at record time
    (e.g. a CREATE operation, where the Okta user id only exists after
    execution). Matches events with a NULL identity_user_id that are
    linked to the given approval and/or operation.
    """

    if related_approval_id is None and related_operation_id is None:
        return []

    query = db.query(IdentityTimelineEvent).filter(
        IdentityTimelineEvent.identity_user_id.is_(None)
    )

    if related_approval_id is not None and related_operation_id is not None:
        query = query.filter(
            (IdentityTimelineEvent.related_approval_id == related_approval_id)
            | (IdentityTimelineEvent.related_operation_id == related_operation_id)
        )
    elif related_approval_id is not None:
        query = query.filter(
            IdentityTimelineEvent.related_approval_id == related_approval_id
        )
    else:
        query = query.filter(
            IdentityTimelineEvent.related_operation_id == related_operation_id
        )

    rows = query.all()

    for row in rows:
        row.identity_user_id = target_user_id
        if target_user_email:
            row.identity_email = target_user_email

    if rows:
        db.commit()

    return rows


def record_event(
    db,
    event_category,
    event_type,
    identity_user_id=None,
    identity_email=None,
    description=None,
    actor_email=None,
    old_value=None,
    new_value=None,
    related_approval_id=None,
    related_operation_id=None
):
    """
    Shared write path for Category 11 timeline events, used by both
    approval_service and lifecycle_execution_service. Kept as its own
    module (depending only on db/models_lifecycle.py) so neither of
    those two services needs to import the other just to log a timeline
    entry.
    """

    event = IdentityTimelineEvent(
        identity_user_id=identity_user_id,
        identity_email=identity_email,
        event_category=event_category,
        event_type=event_type,
        description=description,
        actor_email=actor_email,
        old_value=old_value,
        new_value=new_value,
        related_approval_id=related_approval_id,
        related_operation_id=related_operation_id
    )

    db.add(event)
    db.commit()

    return event
