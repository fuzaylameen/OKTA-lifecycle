"""
Category 7 - Lifecycle execution tests (dry-run / confirm / execution /
cancel / verify), exercised through /api/lifecycle and /api/approvals
using the TestClient. All Okta-facing work is served by the AsyncMock
user_service/group_service singletons injected via conftest.py -
nothing here reaches OktaClient.request().
"""

import datetime

from app.services import lifecycle_execution_service
from app.db.models_lifecycle import ApprovalRequest
from tests.conftest import TestSessionLocal


APPROVAL_NOT_REQUIRED_POLICY = {
    "approval_required": False,
    "required_levels": [],
    "reason": "No approval required for this test scenario.",
    "source": "TEST_OVERRIDE",
}

APPROVAL_REQUIRED_POLICY = {
    "approval_required": True,
    "required_levels": ["MANAGER"],
    "reason": "Approval required for this test scenario.",
    "source": "TEST_OVERRIDE",
}

NO_RISK_DATA = {
    "risk_score": None,
    "risk_band": None,
    "reason": "No risk engine in this test.",
    "source": "TEST_OVERRIDE",
}

NO_IMPACT_DATA = {
    "impact_level": None,
    "affected_resources": None,
    "reason": "No impact engine in this test.",
    "source": "TEST_OVERRIDE",
}

IMPACT_DATA = {
    "impact_level": "HIGH",
    "affected_resources": ["grpFinance", "appPayroll"],
    "reason": "Deactivation removes access to finance-critical apps.",
    "source": "TEST_OVERRIDE",
}


def _dry_run(client, **overrides):

    payload = {
        "operation_type": "DEACTIVATE",
        "requested_by": "requester@example.com",
        "target_user_id": "00uTargetUser",
        "target_user_email": "target@example.com",
        "payload": {},
    }
    payload.update(overrides)

    response = client.post("/api/lifecycle/dry-run", json=payload)
    assert response.status_code == 200
    return response.json()["operation"]


def test_dry_run_deactivate_captures_current_state(client, mock_okta_backed_services):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = [
        {"id": "00uTargetUser", "status": "ACTIVE", "profile": {"email": "target@example.com"}}
    ]

    operation = _dry_run(client)

    assert operation["status"] == "DRY_RUN"
    assert operation["preview"]["current_state"]["status"] == "ACTIVE"
    assert operation["preview"]["proposed_change"]["action"] == "DEACTIVATE_USER"
    user_mock.list_users.assert_awaited()


def test_dry_run_unsupported_operation_type_returns_400(client):

    response = client.post(
        "/api/lifecycle/dry-run",
        json={
            "operation_type": "NOT_A_REAL_OPERATION",
            "requested_by": "requester@example.com",
        },
    )

    assert response.status_code == 400


def test_get_operation_not_found(client):

    response = client.get("/api/lifecycle/999999")

    assert response.status_code == 404


def test_confirm_without_approval_required_executes_immediately(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []
    user_mock.deactivate_user.return_value = None

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_NOT_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    operation = _dry_run(client)

    response = client.post(f"/api/lifecycle/{operation['id']}/confirm")

    assert response.status_code == 200
    body = response.json()["operation"]
    assert body["status"] == "EXECUTED"
    assert body["approval_request_id"] is None
    user_mock.deactivate_user.assert_awaited_once_with("00uTargetUser")


def test_confirm_with_approval_required_then_approve_executes(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []
    user_mock.deactivate_user.return_value = None

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    operation = _dry_run(client)

    confirmed = client.post(f"/api/lifecycle/{operation['id']}/confirm").json()["operation"]

    assert confirmed["status"] == "PENDING_APPROVAL"
    approval_id = confirmed["approval_request_id"]
    assert approval_id is not None

    user_mock.deactivate_user.assert_not_awaited()

    approve_response = client.post(
        f"/api/approvals/{approval_id}/approve",
        json={"approver_email": "manager@example.com"},
    )
    assert approve_response.status_code == 200

    final_operation = client.get(f"/api/lifecycle/{operation['id']}").json()

    assert final_operation["status"] == "EXECUTED"
    user_mock.deactivate_user.assert_awaited_once_with("00uTargetUser")


def test_confirm_then_reject_cancels_operation(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    operation = _dry_run(client)
    confirmed = client.post(f"/api/lifecycle/{operation['id']}/confirm").json()["operation"]
    approval_id = confirmed["approval_request_id"]

    client.post(
        f"/api/approvals/{approval_id}/reject",
        json={"approver_email": "manager@example.com", "comment": "not needed"},
    )

    final_operation = client.get(f"/api/lifecycle/{operation['id']}").json()

    assert final_operation["status"] == "CANCELLED"
    user_mock.deactivate_user.assert_not_awaited()


def test_confirm_twice_is_conflict(client, mock_okta_backed_services, monkeypatch):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_NOT_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    operation = _dry_run(client)
    client.post(f"/api/lifecycle/{operation['id']}/confirm")

    second = client.post(f"/api/lifecycle/{operation['id']}/confirm")

    assert second.status_code == 409


def test_cancel_from_dry_run(client, mock_okta_backed_services):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []

    operation = _dry_run(client)

    response = client.post(f"/api/lifecycle/{operation['id']}/cancel")

    assert response.status_code == 200
    assert response.json()["operation"]["status"] == "CANCELLED"


def test_cancel_from_pending_approval(client, mock_okta_backed_services, monkeypatch):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    operation = _dry_run(client)
    confirmed = client.post(f"/api/lifecycle/{operation['id']}/confirm").json()["operation"]

    response = client.post(f"/api/lifecycle/{confirmed['id']}/cancel")

    assert response.status_code == 200
    assert response.json()["operation"]["status"] == "CANCELLED"


def test_cancel_after_execution_is_conflict(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_NOT_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    operation = _dry_run(client)
    client.post(f"/api/lifecycle/{operation['id']}/confirm")

    response = client.post(f"/api/lifecycle/{operation['id']}/cancel")

    assert response.status_code == 409


def test_verify_before_execution_is_conflict(client, mock_okta_backed_services):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []

    operation = _dry_run(client)

    response = client.get(f"/api/lifecycle/{operation['id']}/verify")

    assert response.status_code == 409


def test_verify_after_execution_reports_current_state(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_NOT_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    # dry-run reads the pre-execution snapshot
    user_mock.list_users.return_value = [
        {"id": "00uTargetUser", "status": "ACTIVE"}
    ]
    operation = _dry_run(client)

    client.post(f"/api/lifecycle/{operation['id']}/confirm")

    # verify() re-reads the snapshot post-execution
    user_mock.list_users.return_value = [
        {"id": "00uTargetUser", "status": "DEACTIVATED"}
    ]

    response = client.get(f"/api/lifecycle/{operation['id']}/verify")

    assert response.status_code == 200
    body = response.json()["operation"]
    assert body["verification_result"]["current_state"]["status"] == "DEACTIVATED"


def test_bulk_deactivate_dry_run_confirm_and_verify(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_NOT_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    user_ids = ["00uUserA", "00uUserB"]

    operation = _dry_run(
        client,
        operation_type="BULK_DEACTIVATE",
        target_user_id=None,
        target_user_email=None,
        payload={"user_ids": user_ids},
    )

    assert operation["preview"]["proposed_change"]["user_ids"] == user_ids

    user_mock.bulk_deactivate.return_value = {
        "total": 2,
        "successful": 2,
        "failed": 0,
        "results": [
            {"user_id": "00uUserA", "status": "deactivated"},
            {"user_id": "00uUserB", "status": "deactivated"},
        ],
    }

    confirmed = client.post(f"/api/lifecycle/{operation['id']}/confirm").json()["operation"]
    assert confirmed["status"] == "EXECUTED"
    user_mock.bulk_deactivate.assert_awaited_once_with(user_ids)

    user_mock.list_users.return_value = [
        {"id": "00uUserA", "status": "DEACTIVATED"},
        {"id": "00uUserB", "status": "DEACTIVATED"},
    ]

    verified = client.get(f"/api/lifecycle/{confirmed['id']}/verify").json()["operation"]

    assert verified["verification_result"]["all_verified"] is True
    assert verified["verification_result"]["checked_count"] == 2


def test_group_move_confirm_calls_group_service(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, group_mock = mock_okta_backed_services
    user_mock.list_users.return_value = []

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_NOT_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    operation = _dry_run(
        client,
        operation_type="GROUP_MOVE",
        payload={"old_group_id": "grpOld", "new_group_id": "grpNew"},
    )

    confirmed = client.post(f"/api/lifecycle/{operation['id']}/confirm").json()["operation"]

    assert confirmed["status"] == "EXECUTED"
    group_mock.move_user.assert_awaited_once_with("00uTargetUser", "grpOld", "grpNew")


def test_create_operation_backfills_identity_after_execution(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_NOT_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    user_mock.create_user.return_value = {
        "id": "00uBrandNewUser",
        "status": "STAGED",
    }

    operation = _dry_run(
        client,
        operation_type="CREATE",
        target_user_id=None,
        target_user_email=None,
        payload={
            "first_name": "New",
            "last_name": "Hire",
            "email": "new.hire@example.com",
        },
    )

    confirmed = client.post(f"/api/lifecycle/{operation['id']}/confirm").json()["operation"]

    assert confirmed["status"] == "EXECUTED"
    assert confirmed["target_user_id"] == "00uBrandNewUser"
    assert confirmed["target_user_email"] == "new.hire@example.com"
    user_mock.create_user.assert_awaited_once_with(
        {
            "first_name": "New",
            "last_name": "Hire",
            "email": "new.hire@example.com",
        }
    )


# --- Gap: CREATE with approval required - full identity/timeline backfill ---


def test_create_with_approval_required_backfills_identity_and_timeline(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    user_mock.create_user.return_value = {
        "id": "00uApprovedNewUser",
        "status": "STAGED",
    }

    operation = _dry_run(
        client,
        operation_type="CREATE",
        target_user_id=None,
        target_user_email=None,
        payload={
            "first_name": "Approved",
            "last_name": "Hire",
            "email": "new.hire2@example.com",
        },
    )

    confirmed = client.post(f"/api/lifecycle/{operation['id']}/confirm").json()["operation"]

    assert confirmed["status"] == "PENDING_APPROVAL"
    approval_id = confirmed["approval_request_id"]
    assert approval_id is not None

    # Before execution, the approval has no known identity yet (the Okta
    # user doesn't exist until CREATE actually runs).
    approval_before = client.get(f"/api/approvals/{approval_id}").json()
    assert approval_before["target_user_id"] is None

    user_mock.create_user.assert_not_awaited()

    approve_response = client.post(
        f"/api/approvals/{approval_id}/approve",
        json={"approver_email": "manager@example.com"},
    )
    assert approve_response.status_code == 200

    user_mock.create_user.assert_awaited_once()

    final_operation = client.get(f"/api/lifecycle/{operation['id']}").json()

    assert final_operation["status"] == "EXECUTED"
    assert final_operation["target_user_id"] == "00uApprovedNewUser"
    assert final_operation["target_user_email"] == "new.hire2@example.com"

    # The approval-linked identity must also be backfilled once known.
    approval_after = client.get(f"/api/approvals/{approval_id}").json()
    assert approval_after["target_user_id"] == "00uApprovedNewUser"
    assert approval_after["target_user_email"] == "new.hire2@example.com"

    # All timeline events recorded before the identity was known (dry-run
    # policy/risk preview, approval request, approval decision) must be
    # backfilled onto the new user's timeline, alongside the execution
    # event recorded with the identity already known.
    timeline = client.get("/api/timeline/00uApprovedNewUser").json()
    event_types = {event["event_type"] for event in timeline}
    sources = {event["source"] for event in timeline}

    assert "POLICY_PREVIEWED" in event_types
    assert "RISK_PREVIEWED" in event_types
    assert "APPROVAL_REQUESTED" in event_types
    assert "OPERATION_EXECUTED" in event_types
    assert "TIMELINE_EVENT" in sources
    assert "APPROVAL_STEP" in sources


# --- Gap: PROVISION full lifecycle ---


def test_provision_dry_run_confirm_execute_verify(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_NOT_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    user_mock.list_users.return_value = [
        {"id": "00uProvUser", "status": "STAGED"}
    ]

    operation = _dry_run(
        client,
        operation_type="PROVISION",
        target_user_id="00uProvUser",
        target_user_email="prov.user@example.com",
    )

    assert operation["preview"]["current_state"]["status"] == "STAGED"
    assert operation["preview"]["proposed_change"]["action"] == "ACTIVATE_USER"

    user_mock.provision_user.return_value = {
        "id": "00uProvUser",
        "status": "PROVISIONED",
    }

    confirmed = client.post(f"/api/lifecycle/{operation['id']}/confirm").json()["operation"]

    assert confirmed["status"] == "EXECUTED"
    user_mock.provision_user.assert_awaited_once_with("00uProvUser")

    user_mock.list_users.return_value = [
        {"id": "00uProvUser", "status": "ACTIVE"}
    ]

    verified = client.get(f"/api/lifecycle/{confirmed['id']}/verify").json()["operation"]

    assert verified["verification_result"]["current_state"]["status"] == "ACTIVE"


# --- Gap: DELETE full lifecycle ---


def test_delete_dry_run_confirm_execute_verify(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_NOT_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    user_mock.list_users.return_value = [
        {"id": "00uDelUser", "status": "DEACTIVATED"}
    ]

    operation = _dry_run(
        client,
        operation_type="DELETE",
        target_user_id="00uDelUser",
        target_user_email="del.user@example.com",
    )

    assert operation["preview"]["current_state"]["status"] == "DEACTIVATED"
    assert operation["preview"]["proposed_change"]["action"] == "DELETE_USER"

    user_mock.delete_user.return_value = None

    confirmed = client.post(f"/api/lifecycle/{operation['id']}/confirm").json()["operation"]

    assert confirmed["status"] == "EXECUTED"
    user_mock.delete_user.assert_awaited_once_with("00uDelUser")

    # After deletion the user no longer appears in Okta's user list.
    user_mock.list_users.return_value = []

    verified = client.get(f"/api/lifecycle/{confirmed['id']}/verify").json()["operation"]

    assert verified["verification_result"]["current_state"] is None


# --- Gap: execution failure path ---


def test_execution_failure_marks_operation_failed_and_records_event(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []
    user_mock.deactivate_user.side_effect = RuntimeError("Simulated Okta outage")

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_NOT_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    operation = _dry_run(
        client,
        target_user_id="00uFailUser",
        target_user_email="fail.user@example.com",
    )

    response = client.post(f"/api/lifecycle/{operation['id']}/confirm")

    assert response.status_code == 500
    assert "Simulated Okta outage" in response.json()["detail"]

    failed_operation = client.get(f"/api/lifecycle/{operation['id']}").json()

    assert failed_operation["status"] == "FAILED"
    assert failed_operation["executed_at"] is None

    timeline = client.get("/api/timeline/00uFailUser").json()
    failure_events = [e for e in timeline if e["event_type"] == "OPERATION_FAILED"]

    assert len(failure_events) == 1
    assert "Simulated Okta outage" in failure_events[0]["description"]


# --- Gap: approval expiry deterministically forces CANCELLED, not executed ---


async def test_finalize_operation_on_expired_approval_cancels_without_executing(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    operation = _dry_run(client, target_user_id="00uExpireUser", target_user_email="expire.user@example.com")
    confirmed = client.post(f"/api/lifecycle/{operation['id']}/confirm").json()["operation"]

    approval_id = confirmed["approval_request_id"]
    assert approval_id is not None

    # Deterministically force the approval into the past so the lazy
    # expiry check in approval_service will flip it to EXPIRED.
    db = TestSessionLocal()
    try:
        approval_row = db.query(ApprovalRequest).filter_by(id=approval_id).first()
        approval_row.expires_at = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        db.commit()

        finalized_operation = await lifecycle_execution_service.finalize_operation(
            db, operation["id"]
        )
        finalized_status = finalized_operation.status
    finally:
        db.close()

    assert finalized_status == "CANCELLED"
    user_mock.deactivate_user.assert_not_awaited()

    approval_after = client.get(f"/api/approvals/{approval_id}").json()
    assert approval_after["status"] == "EXPIRED"

    operation_after = client.get(f"/api/lifecycle/{operation['id']}").json()
    assert operation_after["status"] == "CANCELLED"


# --- Gap: BULK_DEACTIVATE partial failure must not report full success ---


def test_bulk_deactivate_partial_failure_reports_correctly(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_NOT_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    user_ids = ["00uUserGood", "00uUserBad"]

    operation = _dry_run(
        client,
        operation_type="BULK_DEACTIVATE",
        target_user_id=None,
        target_user_email=None,
        payload={"user_ids": user_ids},
    )

    user_mock.bulk_deactivate.return_value = {
        "total": 2,
        "successful": 1,
        "failed": 1,
        "results": [
            {"user_id": "00uUserGood", "status": "deactivated"},
            {
                "user_id": "00uUserBad",
                "status": "failed",
                "error": "Simulated per-user Okta failure",
            },
        ],
    }

    confirmed = client.post(f"/api/lifecycle/{operation['id']}/confirm").json()["operation"]

    # Execution itself still completes - bulk_deactivate reports partial
    # per-user results internally rather than raising.
    assert confirmed["status"] == "EXECUTED"

    # Fresh Okta snapshot: the "good" user is now deactivated, the "bad"
    # one is still active because its individual deactivation failed.
    user_mock.list_users.return_value = [
        {"id": "00uUserGood", "status": "DEACTIVATED"},
        {"id": "00uUserBad", "status": "ACTIVE"},
    ]

    verified = client.get(f"/api/lifecycle/{confirmed['id']}/verify").json()["operation"]
    verification = verified["verification_result"]

    assert verification["all_verified"] is False
    assert verification["checked_count"] == 2

    by_user_id = {r["user_id"]: r for r in verification["results"]}

    assert by_user_id["00uUserGood"]["verified"] is True
    assert by_user_id["00uUserGood"]["current_status"] == "DEACTIVATED"

    assert by_user_id["00uUserBad"]["verified"] is False
    assert by_user_id["00uUserBad"]["current_status"] == "ACTIVE"


# --- Impact analysis (Category 7) ---


def test_dry_run_defaults_to_impact_engine_unavailable_when_no_impact_service(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_NOT_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    operation = _dry_run(client)

    impact_decision = operation["preview"]["impact_decision"]

    assert impact_decision["source"] == "ENGINE_UNAVAILABLE"
    assert impact_decision["impact_level"] is None
    assert impact_decision["affected_resources"] is None


def test_dry_run_captures_impact_decision_from_engine(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_NOT_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_impact",
        lambda *a, **k: IMPACT_DATA,
    )

    operation = _dry_run(client)

    impact_decision = operation["preview"]["impact_decision"]

    assert impact_decision["impact_level"] == "HIGH"
    assert impact_decision["affected_resources"] == ["grpFinance", "appPayroll"]
    assert impact_decision["source"] == "TEST_OVERRIDE"


def test_dry_run_records_impact_previewed_timeline_event(
    client, mock_okta_backed_services, monkeypatch
):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: APPROVAL_NOT_REQUIRED_POLICY,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_impact",
        lambda *a, **k: IMPACT_DATA,
    )

    _dry_run(
        client,
        target_user_id="00uImpactUser",
        target_user_email="impact.user@example.com",
    )

    timeline = client.get("/api/timeline/00uImpactUser").json()
    impact_events = [e for e in timeline if e["event_type"] == "IMPACT_PREVIEWED"]

    assert len(impact_events) == 1
    assert impact_events[0]["category"] == "IMPACT_ANALYSIS"
    assert "HIGH" in impact_events[0]["description"]
    assert "TEST_OVERRIDE" in impact_events[0]["description"]
