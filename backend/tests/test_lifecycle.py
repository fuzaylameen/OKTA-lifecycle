"""
Category 7 - Lifecycle execution tests (dry-run / confirm / execution /
cancel / verify), exercised through /api/lifecycle and /api/approvals
using the TestClient. All Okta-facing work is served by the AsyncMock
user_service/group_service singletons injected via conftest.py -
nothing here reaches OktaClient.request().
"""

import datetime

from unittest.mock import AsyncMock

import httpx
import pytest

from app.integrations.impact_engine_client import evaluate_impact
from app.integrations.policy_engine_client import evaluate_policy
from app.services import lifecycle_execution_service
from app.services import impact_service
from app.services import policy_service
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
    """
    app.services.impact_service now exists (Category 7 is implemented),
    so the ImportError fallback in impact_engine_client can no longer
    occur naturally. This test still exercises that fallback path by
    forcing the import to fail, the same way it would if the module
    were absent - see impact_engine_client.py's documented contract.
    """

    import sys

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
    monkeypatch.setitem(sys.modules, "app.services.impact_service", None)

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
        AsyncMock(return_value=IMPACT_DATA),
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
        AsyncMock(return_value=IMPACT_DATA),
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


# --- impact_service.evaluate() access-preview logic (Category 7) ---


def _mock_impact_services(monkeypatch, group_apps=None, user_groups=None):
    """
    Replaces impact_service's own group_service/user_service singletons
    (independent from the ones lifecycle_execution_service uses) with
    AsyncMocks, so evaluate() never reaches OktaClient.

    group_apps: dict of group_id -> list of app dicts, used as the
    side_effect for group_service.list_apps(group_id).
    user_groups: dict of user_id -> list of group dicts, used as the
    side_effect for user_service.list_user_groups(user_id).
    """

    group_mock = AsyncMock(name="MockImpactGroupService")
    user_mock = AsyncMock(name="MockImpactUserService")

    group_apps = group_apps or {}
    user_groups = user_groups or {}

    group_mock.list_apps.side_effect = (
        lambda group_id: group_apps.get(group_id, [])
    )
    user_mock.list_user_groups.side_effect = (
        lambda user_id: user_groups.get(user_id, [])
    )

    monkeypatch.setattr(impact_service, "group_service", group_mock)
    monkeypatch.setattr(impact_service, "user_service", user_mock)

    return group_mock, user_mock


async def test_impact_service_group_move_computes_apps_gained_and_lost(monkeypatch):

    _mock_impact_services(
        monkeypatch,
        group_apps={
            "grpOld": [
                {"id": "appPayroll", "label": "Payroll"},
                {"id": "appHR", "label": "HR"},
            ],
            "grpNew": [
                {"id": "appHR", "label": "HR"},
                {"id": "appFinance", "label": "Finance"},
            ],
        },
    )

    decision = await impact_service.evaluate(
        "GROUP_MOVE",
        "00uTargetUser",
        {"old_group_id": "grpOld", "new_group_id": "grpNew"},
    )

    by_app = {r["app_id"]: r["change"] for r in decision["affected_resources"]}

    assert by_app == {"appPayroll": "LOST", "appFinance": "GAINED"}
    assert "appHR" not in by_app
    assert decision["groups_removed"] == ["grpOld"]
    assert decision["groups_added"] == ["grpNew"]
    assert decision["impact_level"] == "MEDIUM"


async def test_impact_service_group_move_no_change_is_low_impact(monkeypatch):

    _mock_impact_services(
        monkeypatch,
        group_apps={
            "grpOld": [{"id": "appHR", "label": "HR"}],
            "grpNew": [{"id": "appHR", "label": "HR"}],
        },
    )

    decision = await impact_service.evaluate(
        "GROUP_MOVE",
        "00uTargetUser",
        {"old_group_id": "grpOld", "new_group_id": "grpNew"},
    )

    assert decision["affected_resources"] == []
    assert decision["impact_level"] == "LOW"


async def test_impact_service_deactivate_identifies_access_to_be_removed(monkeypatch):

    _mock_impact_services(
        monkeypatch,
        group_apps={
            "grp1": [{"id": "appA", "label": "App A"}],
            "grp2": [{"id": "appB", "label": "App B"}],
        },
        user_groups={
            "00uTargetUser": [{"id": "grp1"}, {"id": "grp2"}],
        },
    )

    decision = await impact_service.evaluate(
        "DEACTIVATE", "00uTargetUser", {}
    )

    by_app = {r["app_id"]: r["change"] for r in decision["affected_resources"]}

    assert by_app == {"appA": "LOST", "appB": "LOST"}
    assert set(decision["groups_removed"]) == {"grp1", "grp2"}
    assert decision["groups_added"] == []


async def test_impact_service_delete_identifies_access_to_be_removed(monkeypatch):

    _mock_impact_services(
        monkeypatch,
        group_apps={"grp1": [{"id": "appA", "label": "App A"}]},
        user_groups={"00uTargetUser": [{"id": "grp1"}]},
    )

    decision = await impact_service.evaluate(
        "DELETE", "00uTargetUser", {}
    )

    assert decision["affected_resources"] == [
        {"app_id": "appA", "app_name": "App A", "change": "LOST"}
    ]


async def test_impact_service_bulk_deactivate_aggregates_across_users(monkeypatch):

    _mock_impact_services(
        monkeypatch,
        group_apps={
            "grp1": [{"id": "appA", "label": "App A"}],
            "grp2": [{"id": "appB", "label": "App B"}],
        },
        user_groups={
            "00uUserOne": [{"id": "grp1"}],
            "00uUserTwo": [{"id": "grp2"}],
        },
    )

    decision = await impact_service.evaluate(
        "BULK_DEACTIVATE",
        None,
        {"user_ids": ["00uUserOne", "00uUserTwo"]},
    )

    by_app = {r["app_id"]: r["change"] for r in decision["affected_resources"]}

    assert by_app == {"appA": "LOST", "appB": "LOST"}
    assert set(decision["groups_removed"]) == {"grp1", "grp2"}


async def test_impact_service_create_with_group_assignments_computes_access_gained(
    monkeypatch,
):

    _mock_impact_services(
        monkeypatch,
        group_apps={
            "grpNew": [{"id": "appC", "label": "App C"}],
        },
    )

    decision = await impact_service.evaluate(
        "CREATE",
        None,
        {"group_ids": ["grpNew"]},
    )

    assert decision["affected_resources"] == [
        {"app_id": "appC", "app_name": "App C", "change": "GAINED"}
    ]
    assert decision["groups_added"] == ["grpNew"]


async def test_impact_service_provision_without_group_assignments_is_no_op(monkeypatch):

    _mock_impact_services(monkeypatch)

    decision = await impact_service.evaluate("PROVISION", "00uTargetUser", {})

    assert decision["affected_resources"] == []
    assert decision["groups_added"] == []
    assert decision["impact_level"] == "LOW"


async def test_dry_run_group_move_computes_real_access_preview_end_to_end(
    client, mock_okta_backed_services, monkeypatch
):
    """
    Confirms the full wiring: dry-run -> lifecycle_execution_service ->
    impact_engine_client -> impact_service, without stubbing out
    evaluate_impact itself (unlike the other dry-run tests above).
    """

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
    _mock_impact_services(
        monkeypatch,
        group_apps={
            "grpOld": [{"id": "appPayroll", "label": "Payroll"}],
            "grpNew": [{"id": "appFinance", "label": "Finance"}],
        },
    )

    operation = _dry_run(
        client,
        operation_type="GROUP_MOVE",
        payload={"old_group_id": "grpOld", "new_group_id": "grpNew"},
    )

    impact_decision = operation["preview"]["impact_decision"]
    by_app = {
        r["app_id"]: r["change"]
        for r in impact_decision["affected_resources"]
    }

    assert impact_decision["source"] == "ENGINE"
    assert by_app == {"appPayroll": "LOST", "appFinance": "GAINED"}


# --- Impact engine Okta-failure fallback (Category 7) ---


async def test_evaluate_impact_falls_back_when_okta_call_fails(monkeypatch):

    group_mock = AsyncMock(name="MockImpactGroupService")
    group_mock.list_apps.side_effect = httpx.HTTPStatusError(
        "500 Server Error", request=None, response=None
    )

    monkeypatch.setattr(impact_service, "group_service", group_mock)
    monkeypatch.setattr(impact_service, "user_service", AsyncMock())

    decision = await evaluate_impact(
        "GROUP_MOVE",
        "00uTargetUser",
        {"old_group_id": "grpOld", "new_group_id": "grpNew"},
    )

    assert decision["source"] == "ENGINE_ERROR"
    assert decision["impact_level"] is None
    assert decision["affected_resources"] is None
    assert "Okta" in decision["reason"]


async def test_dry_run_group_move_returns_200_when_okta_fails_during_impact_analysis(
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

    group_mock = AsyncMock(name="MockImpactGroupService")
    group_mock.list_apps.side_effect = httpx.RequestError("connection failed")
    monkeypatch.setattr(impact_service, "group_service", group_mock)
    monkeypatch.setattr(impact_service, "user_service", AsyncMock())

    response = client.post(
        "/api/lifecycle/dry-run",
        json={
            "operation_type": "GROUP_MOVE",
            "requested_by": "requester@example.com",
            "target_user_id": "00uTargetUser",
            "target_user_email": "target@example.com",
            "payload": {"old_group_id": "grpOld", "new_group_id": "grpNew"},
        },
    )

    assert response.status_code == 200

    operation = response.json()["operation"]

    assert operation["status"] == "DRY_RUN"
    assert operation["preview"]["impact_decision"]["source"] == "ENGINE_ERROR"
    assert operation["preview"]["impact_decision"]["impact_level"] is None
    assert operation["preview"]["impact_decision"]["affected_resources"] is None


async def test_evaluate_impact_does_not_swallow_non_http_errors(monkeypatch):
    """
    Guards against over-broad exception handling in the adapter: a bug
    in the engine itself (not an Okta/network failure) must still
    propagate rather than being reported as an Okta outage.
    """

    group_mock = AsyncMock(name="MockImpactGroupService")
    group_mock.list_apps.side_effect = TypeError("boom - a real bug")

    monkeypatch.setattr(impact_service, "group_service", group_mock)
    monkeypatch.setattr(impact_service, "user_service", AsyncMock())

    with pytest.raises(TypeError):
        await evaluate_impact(
            "GROUP_MOVE",
            "00uTargetUser",
            {"old_group_id": "grpOld", "new_group_id": "grpNew"},
        )


# --- policy_service.evaluate() static per-operation-type rules (Category 4) ---


@pytest.mark.parametrize(
    "operation_type, expected_approval_required, expected_levels",
    [
        ("CREATE", False, []),
        ("PROVISION", True, ["MANAGER"]),
        ("GROUP_MOVE", True, ["MANAGER"]),
        ("DEACTIVATE", True, ["MANAGER"]),
        ("BULK_DEACTIVATE", True, ["MANAGER", "SECURITY"]),
        ("DELETE", True, ["MANAGER", "SECURITY"]),
    ],
)
def test_policy_service_static_rules_per_operation_type(
    operation_type, expected_approval_required, expected_levels
):

    decision = policy_service.evaluate(operation_type, "00uTargetUser", {})

    assert decision["approval_required"] is expected_approval_required
    assert decision["required_levels"] == expected_levels
    assert decision["reason"]


def test_policy_service_unknown_operation_type_fails_closed():

    decision = policy_service.evaluate("NOT_A_REAL_OPERATION", "00uTargetUser", {})

    assert decision["approval_required"] is True
    assert decision["required_levels"] == ["MANAGER"]


def test_evaluate_policy_defaults_to_engine_unavailable_when_no_policy_service(
    monkeypatch,
):
    """
    app.services.policy_service now exists (Category 4 is implemented),
    so the ImportError fallback in policy_engine_client can no longer
    occur naturally. This test still exercises that fallback path by
    forcing the import to fail, the same way it would if the module
    were absent - see policy_engine_client.py's documented contract.
    """

    import sys

    monkeypatch.setitem(sys.modules, "app.services.policy_service", None)

    decision = evaluate_policy("DEACTIVATE", "00uTargetUser", {})

    assert decision["source"] == "ENGINE_UNAVAILABLE"
    assert decision["approval_required"] is True
    assert decision["required_levels"] == ["MANAGER"]


def test_evaluate_policy_returns_real_engine_result_with_source_engine():

    decision = evaluate_policy("DELETE", "00uTargetUser", {})

    assert decision["source"] == "ENGINE"
    assert decision["approval_required"] is True
    assert decision["required_levels"] == ["MANAGER", "SECURITY"]


def test_dry_run_group_move_computes_real_policy_decision_end_to_end(
    client, mock_okta_backed_services
):
    """
    Confirms the full wiring: dry-run -> lifecycle_execution_service ->
    policy_engine_client -> policy_service, without stubbing out
    evaluate_policy itself.
    """

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []

    operation = _dry_run(
        client,
        operation_type="GROUP_MOVE",
        payload={"old_group_id": "grpOld", "new_group_id": "grpNew"},
    )

    policy_decision = operation["preview"]["policy_decision"]

    assert policy_decision["source"] == "ENGINE"
    assert policy_decision["approval_required"] is True
    assert policy_decision["required_levels"] == ["MANAGER"]


def test_dry_run_create_computes_real_policy_decision_end_to_end(
    client, mock_okta_backed_services
):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []

    operation = _dry_run(
        client,
        operation_type="CREATE",
        target_user_id=None,
        target_user_email=None,
        payload={"first_name": "New", "last_name": "User", "email": "new.user@example.com"},
    )

    policy_decision = operation["preview"]["policy_decision"]

    assert policy_decision["source"] == "ENGINE"
    assert policy_decision["approval_required"] is False
    assert policy_decision["required_levels"] == []
