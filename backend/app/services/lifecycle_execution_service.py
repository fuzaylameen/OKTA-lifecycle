import json
from datetime import datetime

from app.db.models_lifecycle import LifecycleOperation
from app.services import approval_service
from app.services.timeline_recorder import record_event, backfill_identity
from app.services.user_service import UserService
from app.services.group_service import GroupService
from app.integrations.policy_engine_client import evaluate_policy
from app.integrations.risk_engine_client import evaluate_risk
from app.integrations.impact_engine_client import evaluate_impact


# This module is the single owner of the lifecycle execution state
# transition (DRY_RUN -> PENDING_APPROVAL -> EXECUTED/CANCELLED/FAILED
# -> verified). It depends on approval_service (one-way) to create
# approval requests and read their status; approval_service has no
# dependency back on this module, which avoids a circular import
# between the two services.
#
# Execution itself is always performed by calling the existing,
# unmodified UserService / GroupService instances - this module never
# talks to Okta directly and never duplicates their logic.

user_service = UserService()
group_service = GroupService()


SUPPORTED_OPERATIONS = {
    "CREATE",
    "PROVISION",
    "DEACTIVATE",
    "BULK_DEACTIVATE",
    "DELETE",
    "GROUP_MOVE",
    "REACTIVATE",
    "PROFILE_UPDATE"
}

OPERATION_TIMELINE_CATEGORY = {
    "CREATE": "CREATION",
    "PROVISION": "ACTIVATION",
    "DEACTIVATE": "SUSPENSION",
    "BULK_DEACTIVATE": "SUSPENSION",
    "DELETE": "OFFBOARDING",
    "GROUP_MOVE": "ACCESS_CHANGE",
    "REACTIVATE": "REACTIVATION",
    "PROFILE_UPDATE": "PROFILE_CHANGE"
}


class LifecycleOperationError(Exception):
    pass


def _describe_proposed_change(operation_type, payload):

    if operation_type == "CREATE":
        return {"action": "CREATE_USER", "profile": payload}

    if operation_type == "PROVISION":
        return {"action": "ACTIVATE_USER"}

    if operation_type == "DEACTIVATE":
        return {"action": "DEACTIVATE_USER"}

    if operation_type == "BULK_DEACTIVATE":
        return {
            "action": "BULK_DEACTIVATE_USERS",
            "user_ids": payload.get("user_ids", [])
        }

    if operation_type == "DELETE":
        return {"action": "DELETE_USER"}

    if operation_type == "GROUP_MOVE":
        return {
            "action": "MOVE_GROUP",
            "old_group_id": payload.get("old_group_id"),
            "new_group_id": payload.get("new_group_id")
        }

    if operation_type == "REACTIVATE":
        return {"action": "REACTIVATE_USER"}

    if operation_type == "PROFILE_UPDATE":
        return {
            "action": "UPDATE_PROFILE",
            "profile_changes": payload.get("profile_changes", {})
        }

    return {}


async def _get_users_snapshot_map():
    """
    Always issues a fresh GET to Okta (via the existing, unmodified
    UserService.list_users()) and indexes the result by user id, so
    both single-user and bulk verification read current state rather
    than anything cached from dry-run time.
    """

    users = await user_service.list_users()

    return {
        user.get("id"): user
        for user in users
        if isinstance(user, dict) and user.get("id")
    }


async def _get_current_user_snapshot(target_user_id):

    if not target_user_id:
        return None

    snapshot_map = await _get_users_snapshot_map()

    return snapshot_map.get(target_user_id)


async def dry_run(
    db,
    operation_type,
    requested_by,
    target_user_id=None,
    target_user_email=None,
    payload=None
):

    operation_type = operation_type.upper()

    if operation_type not in SUPPORTED_OPERATIONS:
        raise LifecycleOperationError(
            f"Unsupported operation_type: {operation_type}"
        )

    payload = payload or {}

    current_state = await _get_current_user_snapshot(target_user_id)

    policy_decision = evaluate_policy(operation_type, target_user_id, payload)
    risk_decision = evaluate_risk(operation_type, target_user_id, payload)
    impact_decision = await evaluate_impact(operation_type, target_user_id, payload)

    preview_payload = {
        "current_state": current_state,
        "proposed_change": _describe_proposed_change(operation_type, payload),
        "policy_decision": policy_decision,
        "risk_decision": risk_decision,
        "impact_decision": impact_decision,
        "requested_by": requested_by
    }

    operation = LifecycleOperation(
        operation_type=operation_type,
        target_user_id=target_user_id,
        target_user_email=target_user_email,
        requested_by=requested_by,
        status="DRY_RUN",
        preview_payload=json.dumps(preview_payload)
    )

    db.add(operation)
    db.commit()
    db.refresh(operation)

    record_event(
        db,
        event_category="POLICY_DECISION",
        event_type="POLICY_PREVIEWED",
        identity_user_id=target_user_id,
        identity_email=target_user_email,
        description=(
            f"Policy decision for {operation_type}: "
            f"{'approval required' if policy_decision.get('approval_required') else 'no approval required'} "
            f"(source={policy_decision.get('source')})"
        ),
        actor_email=requested_by,
        related_operation_id=operation.id
    )

    record_event(
        db,
        event_category="RISK_SCORE",
        event_type="RISK_PREVIEWED",
        identity_user_id=target_user_id,
        identity_email=target_user_email,
        description=(
            f"Risk score for {operation_type}: "
            f"{risk_decision.get('risk_score')} "
            f"(source={risk_decision.get('source')})"
        ),
        actor_email=requested_by,
        related_operation_id=operation.id
    )

    record_event(
        db,
        event_category="IMPACT_ANALYSIS",
        event_type="IMPACT_PREVIEWED",
        identity_user_id=target_user_id,
        identity_email=target_user_email,
        description=(
            f"Impact analysis for {operation_type}: "
            f"{impact_decision.get('impact_level')} "
            f"(source={impact_decision.get('source')})"
        ),
        actor_email=requested_by,
        related_operation_id=operation.id
    )

    return operation


def get_operation(db, operation_id):

    operation = (
        db.query(LifecycleOperation)
        .filter(LifecycleOperation.id == operation_id)
        .first()
    )

    if not operation:
        raise LifecycleOperationError(
            f"Lifecycle operation {operation_id} not found"
        )

    return operation


async def confirm(db, operation_id):

    operation = get_operation(db, operation_id)

    if operation.status != "DRY_RUN":
        raise LifecycleOperationError(
            f"Operation {operation_id} cannot be confirmed from status "
            f"{operation.status}"
        )

    preview = (
        json.loads(operation.preview_payload)
        if operation.preview_payload else {}
    )

    policy_decision = preview.get("policy_decision", {})
    approval_required = bool(policy_decision.get("approval_required"))

    if not approval_required:
        return await _execute(db, operation)

    risk_decision = preview.get("risk_decision", {})
    required_levels = policy_decision.get("required_levels") or ["MANAGER"]

    approval = approval_service.create_approval_request(
        db,
        operation_type=operation.operation_type,
        requested_by=operation.requested_by,
        required_levels=required_levels,
        target_user_id=operation.target_user_id,
        target_user_email=operation.target_user_email,
        payload=preview.get("proposed_change"),
        risk_score=risk_decision.get("risk_score"),
        risk_band=risk_decision.get("risk_band"),
        policy_source=policy_decision.get("source")
    )

    operation.approval_request_id = approval.id
    operation.status = "PENDING_APPROVAL"
    operation.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(operation)

    return operation


async def finalize_operation(db, operation_id):
    """
    Called after an approval decision is recorded (see routers/approvals.py).
    Reads the current approval status and drives the operation to its
    next state. No-op if the operation is not awaiting approval.
    """

    operation = get_operation(db, operation_id)

    if operation.status != "PENDING_APPROVAL":
        return operation

    status_info = approval_service.get_status(db, operation.approval_request_id)

    if status_info["status"] == "APPROVED":
        return await _execute(db, operation)

    if status_info["status"] in ("REJECTED", "EXPIRED"):

        operation.status = "CANCELLED"
        operation.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(operation)

        record_event(
            db,
            event_category=OPERATION_TIMELINE_CATEGORY.get(
                operation.operation_type, "OTHER"
            ),
            event_type="OPERATION_CANCELLED",
            identity_user_id=operation.target_user_id,
            identity_email=operation.target_user_email,
            description=(
                f"Operation {operation.operation_type} cancelled: "
                f"approval {status_info['status']}"
            ),
            related_operation_id=operation.id,
            related_approval_id=operation.approval_request_id
        )

    return operation


def _link_created_identity(db, operation, result, payload):
    """
    Bug fix: for CREATE, the Okta user id only exists after execution,
    so the LifecycleOperation, the linked ApprovalRequest (if this
    CREATE required approval), and any timeline events recorded during
    dry-run/confirm (which had no identity to attach to yet) all need
    to be backfilled with the real target_user_id/email once the user
    has actually been created in Okta.
    """

    new_user_id = result.get("id") if isinstance(result, dict) else None

    profile = payload.get("profile") if isinstance(payload, dict) else None
    new_email = (
        (profile or {}).get("email")
        or operation.target_user_email
    )

    operation.target_user_id = new_user_id
    operation.target_user_email = new_email

    if operation.approval_request_id:
        approval_service.update_target_identity(
            db,
            operation.approval_request_id,
            new_user_id,
            new_email
        )

    backfill_identity(
        db,
        target_user_id=new_user_id,
        target_user_email=new_email,
        related_approval_id=operation.approval_request_id,
        related_operation_id=operation.id
    )


async def _execute(db, operation):

    payload = (
        json.loads(operation.preview_payload).get("proposed_change", {})
        if operation.preview_payload else {}
    )

    try:

        if operation.operation_type == "CREATE":
            result = await user_service.create_user(payload.get("profile", {}))

        elif operation.operation_type == "PROVISION":
            result = await user_service.provision_user(operation.target_user_id)

        elif operation.operation_type == "DEACTIVATE":
            result = await user_service.deactivate_user(operation.target_user_id)

        elif operation.operation_type == "BULK_DEACTIVATE":
            result = await user_service.bulk_deactivate(payload.get("user_ids", []))

        elif operation.operation_type == "DELETE":
            result = await user_service.delete_user(operation.target_user_id)

        elif operation.operation_type == "GROUP_MOVE":
            result = await group_service.move_user(
                operation.target_user_id,
                payload.get("old_group_id"),
                payload.get("new_group_id")
            )

        elif operation.operation_type == "REACTIVATE":
            result = await user_service.reactivate_user(operation.target_user_id)

        elif operation.operation_type == "PROFILE_UPDATE":
            result = await user_service.update_profile(
                operation.target_user_id,
                payload.get("profile_changes", {})
            )

        else:
            raise LifecycleOperationError(
                f"Unsupported operation_type: {operation.operation_type}"
            )

    except Exception as exc:

        operation.status = "FAILED"
        operation.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(operation)

        record_event(
            db,
            event_category=OPERATION_TIMELINE_CATEGORY.get(
                operation.operation_type, "OTHER"
            ),
            event_type="OPERATION_FAILED",
            identity_user_id=operation.target_user_id,
            identity_email=operation.target_user_email,
            description=f"Execution failed: {exc}",
            related_operation_id=operation.id,
            related_approval_id=operation.approval_request_id
        )

        raise

    if operation.operation_type == "CREATE":
        _link_created_identity(db, operation, result, payload)

    operation.status = "EXECUTED"
    operation.executed_payload = json.dumps(
        result if isinstance(result, (dict, list)) else {"result": str(result)}
    )
    operation.executed_at = datetime.utcnow()
    operation.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(operation)

    old_value = None
    new_value = None

    if operation.operation_type == "GROUP_MOVE":
        old_value = payload.get("old_group_id")
        new_value = payload.get("new_group_id")

    record_event(
        db,
        event_category=OPERATION_TIMELINE_CATEGORY.get(
            operation.operation_type, "OTHER"
        ),
        event_type="OPERATION_EXECUTED",
        identity_user_id=operation.target_user_id,
        identity_email=operation.target_user_email,
        description=f"Executed {operation.operation_type}",
        old_value=old_value,
        new_value=new_value,
        related_operation_id=operation.id,
        related_approval_id=operation.approval_request_id
    )

    return operation


async def cancel(db, operation_id):

    operation = get_operation(db, operation_id)

    if operation.status not in ("DRY_RUN", "PENDING_APPROVAL"):
        raise LifecycleOperationError(
            f"Operation {operation_id} cannot be cancelled from status "
            f"{operation.status}"
        )

    operation.status = "CANCELLED"
    operation.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(operation)

    record_event(
        db,
        event_category=OPERATION_TIMELINE_CATEGORY.get(
            operation.operation_type, "OTHER"
        ),
        event_type="OPERATION_CANCELLED",
        identity_user_id=operation.target_user_id,
        identity_email=operation.target_user_email,
        description=f"Operation {operation.operation_type} cancelled by request",
        related_operation_id=operation.id
    )

    return operation


async def _verify_bulk_deactivate(expected):

    user_ids = expected.get("user_ids", [])

    snapshot_map = await _get_users_snapshot_map()

    results = []
    all_verified = True

    for user_id in user_ids:

        user = snapshot_map.get(user_id)
        current_status = user.get("status") if user else None
        verified = current_status == "DEACTIVATED"

        if not verified:
            all_verified = False

        results.append({
            "user_id": user_id,
            "current_status": current_status,
            "verified": verified
        })

    return {
        "checked_at": datetime.utcnow().isoformat(),
        "expected_action": expected.get("action"),
        "checked_count": len(user_ids),
        "all_verified": all_verified,
        "results": results,
        "note": "Fresh per-user Okta snapshot check for bulk deactivation."
    }


async def verify(db, operation_id):

    operation = get_operation(db, operation_id)

    if operation.status != "EXECUTED":
        raise LifecycleOperationError(
            f"Operation {operation_id} is not in EXECUTED state "
            f"(status={operation.status})"
        )

    expected = (
        json.loads(operation.preview_payload).get("proposed_change", {})
        if operation.preview_payload else {}
    )

    if operation.operation_type == "BULK_DEACTIVATE":

        verification_result = await _verify_bulk_deactivate(expected)

    else:

        current_state = await _get_current_user_snapshot(operation.target_user_id)

        verification_result = {
            "checked_at": datetime.utcnow().isoformat(),
            "current_state": current_state,
            "expected_action": expected.get("action"),
            "note": "Best-effort verification via current Okta user snapshot."
        }

    operation.verification_result = json.dumps(verification_result)
    operation.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(operation)

    record_event(
        db,
        event_category=OPERATION_TIMELINE_CATEGORY.get(
            operation.operation_type, "OTHER"
        ),
        event_type="OPERATION_VERIFIED",
        identity_user_id=operation.target_user_id,
        identity_email=operation.target_user_email,
        description=f"Post-execution verification recorded for {operation.operation_type}",
        related_operation_id=operation.id
    )

    return operation
