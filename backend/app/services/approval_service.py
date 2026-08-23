import json
from datetime import datetime, timedelta

from app.db.models_lifecycle import ApprovalRequest, ApprovalStep
from app.services.timeline_recorder import record_event


DEFAULT_EXPIRY_HOURS = 72
DEFAULT_REQUIRED_LEVELS = ["MANAGER"]

# NOTE: this module intentionally has no dependency on
# lifecycle_execution_service. It only records approval requests and
# decisions. Whoever needs to react to a decision (e.g. execute the
# underlying lifecycle operation) reads the resulting status via
# get_status() / get_approval() - see lifecycle_execution_service.py
# and routers/approvals.py.


class ApprovalNotFoundError(Exception):
    pass


class InvalidApprovalStateError(Exception):
    pass


class SeparationOfDutiesError(Exception):
    pass


def create_approval_request(
    db,
    operation_type,
    requested_by,
    required_levels=None,
    target_user_id=None,
    target_user_email=None,
    payload=None,
    risk_score=None,
    risk_band=None,
    policy_source=None,
    expires_in_hours=None
):

    levels = required_levels or DEFAULT_REQUIRED_LEVELS
    expiry_hours = expires_in_hours or DEFAULT_EXPIRY_HOURS

    approval = ApprovalRequest(
        operation_type=operation_type,
        target_user_id=target_user_id,
        target_user_email=target_user_email,
        requested_by=requested_by,
        status="PENDING",
        current_level=1,
        required_levels=json.dumps(levels),
        payload=json.dumps(payload) if payload is not None else None,
        risk_score=risk_score,
        risk_band=risk_band,
        policy_source=policy_source,
        expires_at=datetime.utcnow() + timedelta(hours=expiry_hours)
    )

    db.add(approval)
    db.commit()
    db.refresh(approval)

    for level, role in enumerate(levels, start=1):

        db.add(ApprovalStep(
            approval_request_id=approval.id,
            level=level,
            approver_role=role,
            decision="PENDING"
        ))

    db.commit()

    record_event(
        db,
        event_category="APPROVAL",
        event_type="APPROVAL_REQUESTED",
        identity_user_id=target_user_id,
        identity_email=target_user_email,
        description=f"Approval requested for {operation_type} "
                     f"({len(levels)} level(s): {', '.join(levels)})",
        actor_email=requested_by,
        related_approval_id=approval.id
    )

    db.refresh(approval)

    return approval


def _apply_expiry_if_needed(db, approval):

    if (
        approval.status == "PENDING"
        and approval.expires_at
        and datetime.utcnow() > approval.expires_at
    ):

        approval.status = "EXPIRED"
        approval.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(approval)

        record_event(
            db,
            event_category="APPROVAL",
            event_type="APPROVAL_EXPIRED",
            identity_user_id=approval.target_user_id,
            identity_email=approval.target_user_email,
            description=f"Approval request {approval.id} expired",
            related_approval_id=approval.id
        )

    return approval


def get_approval(db, approval_id):

    approval = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.id == approval_id)
        .first()
    )

    if not approval:
        raise ApprovalNotFoundError(
            f"Approval request {approval_id} not found"
        )

    return _apply_expiry_if_needed(db, approval)


def update_target_identity(db, approval_id, target_user_id, target_user_email=None):
    """
    Links an approval request to the real Okta identity once it exists.
    Needed for operations like CREATE, where the approval request has to
    be created (and approved) before the Okta user id is known.
    """

    approval = get_approval(db, approval_id)

    approval.target_user_id = target_user_id

    if target_user_email:
        approval.target_user_email = target_user_email

    approval.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(approval)

    return approval


def get_status(db, approval_id):

    approval = get_approval(db, approval_id)

    return {
        "id": approval.id,
        "status": approval.status,
        "current_level": approval.current_level,
        "required_levels": (
            json.loads(approval.required_levels)
            if approval.required_levels else []
        )
    }


def list_queue(db, status=None, approver_role=None):

    query = db.query(ApprovalRequest)

    if status:
        query = query.filter(ApprovalRequest.status == status)

    approvals = query.order_by(ApprovalRequest.created_at.desc()).all()

    approvals = [_apply_expiry_if_needed(db, a) for a in approvals]

    if approver_role:

        filtered = []

        for approval in approvals:

            step = (
                db.query(ApprovalStep)
                .filter(
                    ApprovalStep.approval_request_id == approval.id,
                    ApprovalStep.level == approval.current_level
                )
                .first()
            )

            if step and step.approver_role == approver_role:
                filtered.append(approval)

        approvals = filtered

    return approvals


def get_history(db, approval_id):

    get_approval(db, approval_id)

    return (
        db.query(ApprovalStep)
        .filter(ApprovalStep.approval_request_id == approval_id)
        .order_by(ApprovalStep.level.asc())
        .all()
    )


def decide(db, approval_id, approver_email, decision, comment=None):

    if decision not in ("APPROVED", "REJECTED"):
        raise ValueError("decision must be APPROVED or REJECTED")

    if not approver_email or not approver_email.strip():
        raise ValueError(
            "approver_email is required and cannot be blank"
        )

    approver_email = approver_email.strip()

    approval = get_approval(db, approval_id)

    if approval.status != "PENDING":
        raise InvalidApprovalStateError(
            f"Approval request {approval_id} is not pending "
            f"(status={approval.status})"
        )

    if approver_email == approval.requested_by:
        raise SeparationOfDutiesError(
            "The approver cannot be the same identity as the requester "
            "(separation-of-duties violation)"
        )

    step = (
        db.query(ApprovalStep)
        .filter(
            ApprovalStep.approval_request_id == approval.id,
            ApprovalStep.level == approval.current_level
        )
        .first()
    )

    if not step:
        raise InvalidApprovalStateError(
            f"No pending approval step found at level "
            f"{approval.current_level}"
        )

    step.decision = decision
    step.approver_email = approver_email
    step.comment = comment
    step.decided_at = datetime.utcnow()

    required_levels = (
        json.loads(approval.required_levels)
        if approval.required_levels else []
    )

    if decision == "REJECTED":
        approval.status = "REJECTED"
    else:
        if approval.current_level >= len(required_levels):
            approval.status = "APPROVED"
        else:
            approval.current_level += 1
            approval.status = "PENDING"

    approval.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(approval)

    record_event(
        db,
        event_category="APPROVAL",
        event_type=f"APPROVAL_STEP_{decision}",
        identity_user_id=approval.target_user_id,
        identity_email=approval.target_user_email,
        description=f"Level {step.level} ({step.approver_role}) "
                     f"{decision.lower()} by {approver_email}",
        actor_email=approver_email,
        new_value=decision,
        related_approval_id=approval.id
    )

    return approval


def escalate(db, approval_id, approver_email, comment=None, escalate_to_role="SECURITY"):

    approval = get_approval(db, approval_id)

    if approval.status != "PENDING":
        raise InvalidApprovalStateError(
            f"Approval request {approval_id} is not pending "
            f"(status={approval.status})"
        )

    current_step = (
        db.query(ApprovalStep)
        .filter(
            ApprovalStep.approval_request_id == approval.id,
            ApprovalStep.level == approval.current_level
        )
        .first()
    )

    if not current_step:
        raise InvalidApprovalStateError(
            f"No pending approval step found at level "
            f"{approval.current_level}"
        )

    current_step.decision = "ESCALATED"
    current_step.approver_email = approver_email
    current_step.comment = comment
    current_step.decided_at = datetime.utcnow()

    required_levels = (
        json.loads(approval.required_levels)
        if approval.required_levels else []
    )

    new_level = len(required_levels) + 1
    required_levels.append(escalate_to_role)
    approval.required_levels = json.dumps(required_levels)

    db.add(ApprovalStep(
        approval_request_id=approval.id,
        level=new_level,
        approver_role=escalate_to_role,
        decision="PENDING"
    ))

    approval.current_level = new_level
    approval.status = "PENDING"
    approval.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(approval)

    record_event(
        db,
        event_category="APPROVAL",
        event_type="APPROVAL_ESCALATED",
        identity_user_id=approval.target_user_id,
        identity_email=approval.target_user_email,
        description=f"Escalated to level {new_level} "
                     f"({escalate_to_role}) by {approver_email}",
        actor_email=approver_email,
        related_approval_id=approval.id
    )

    return approval
