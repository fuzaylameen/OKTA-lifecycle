"""
Category 6 - Approval workflow tests, exercised entirely through the
/api/approvals FastAPI endpoints using the TestClient. No Okta traffic:
these flows never touch user_service/group_service at all, but the
autouse fixtures in conftest.py still guarantee isolation and block
any live calls.
"""


def _create_approval(client, **overrides):

    payload = {
        "operation_type": "DEACTIVATE",
        "requested_by": "requester@example.com",
        "required_levels": ["MANAGER"],
        "target_user_id": "00uTargetUser",
        "target_user_email": "target@example.com",
        "payload": {"action": "DEACTIVATE_USER"},
    }
    payload.update(overrides)

    response = client.post("/api/approvals/", json=payload)
    assert response.status_code == 200
    return response.json()["approval"]


def test_create_approval_request(client):

    approval = _create_approval(client)

    assert approval["status"] == "PENDING"
    assert approval["current_level"] == 1
    assert approval["operation_type"] == "DEACTIVATE"
    assert approval["target_user_id"] == "00uTargetUser"
    assert approval["id"] is not None


def test_get_approval_by_id(client):

    created = _create_approval(client)

    response = client.get(f"/api/approvals/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_approval_not_found(client):

    response = client.get("/api/approvals/999999")

    assert response.status_code == 404


def test_list_queue_default(client):

    _create_approval(client, requested_by="alice@example.com")
    _create_approval(client, requested_by="bob@example.com")

    response = client.get("/api/approvals/")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2


def test_list_queue_filtered_by_status(client):

    approval = _create_approval(client)

    client.post(
        f"/api/approvals/{approval['id']}/approve",
        json={"approver_email": "manager@example.com"},
    )

    pending = client.get("/api/approvals/", params={"status": "PENDING"}).json()
    approved = client.get("/api/approvals/", params={"status": "APPROVED"}).json()

    assert pending == []
    assert len(approved) == 1
    assert approved[0]["id"] == approval["id"]


def test_list_queue_filtered_by_approver_role(client):

    _create_approval(client, required_levels=["MANAGER"])
    _create_approval(client, required_levels=["SECURITY"])

    manager_queue = client.get(
        "/api/approvals/", params={"approver_role": "MANAGER"}
    ).json()

    assert len(manager_queue) == 1
    assert manager_queue[0]["current_level"] == 1


def test_approve_single_level_moves_to_approved(client):

    approval = _create_approval(client, required_levels=["MANAGER"])

    response = client.post(
        f"/api/approvals/{approval['id']}/approve",
        json={"approver_email": "manager@example.com", "comment": "looks fine"},
    )

    assert response.status_code == 200
    body = response.json()["approval"]
    assert body["status"] == "APPROVED"


def test_approve_multi_level_advances_then_completes(client):

    approval = _create_approval(client, required_levels=["MANAGER", "SECURITY"])

    step1 = client.post(
        f"/api/approvals/{approval['id']}/approve",
        json={"approver_email": "manager@example.com"},
    ).json()["approval"]

    assert step1["status"] == "PENDING"
    assert step1["current_level"] == 2

    step2 = client.post(
        f"/api/approvals/{approval['id']}/approve",
        json={"approver_email": "security@example.com"},
    ).json()["approval"]

    assert step2["status"] == "APPROVED"


def test_reject_sets_status_rejected(client):

    approval = _create_approval(client)

    response = client.post(
        f"/api/approvals/{approval['id']}/reject",
        json={"approver_email": "manager@example.com", "comment": "denied"},
    )

    assert response.status_code == 200
    assert response.json()["approval"]["status"] == "REJECTED"


def test_approve_separation_of_duties_violation(client):

    approval = _create_approval(client, requested_by="same@example.com")

    response = client.post(
        f"/api/approvals/{approval['id']}/approve",
        json={"approver_email": "same@example.com"},
    )

    assert response.status_code == 403


def test_approve_already_decided_is_conflict(client):

    approval = _create_approval(client, required_levels=["MANAGER"])

    client.post(
        f"/api/approvals/{approval['id']}/approve",
        json={"approver_email": "manager@example.com"},
    )

    response = client.post(
        f"/api/approvals/{approval['id']}/approve",
        json={"approver_email": "manager2@example.com"},
    )

    assert response.status_code == 409


def test_escalate_adds_new_level_and_requires_new_decision(client):

    approval = _create_approval(client, required_levels=["MANAGER"])

    response = client.post(
        f"/api/approvals/{approval['id']}/escalate",
        json={"approver_email": "manager@example.com", "escalate_to_role": "SECURITY"},
    )

    assert response.status_code == 200
    body = response.json()["approval"]
    assert body["status"] == "PENDING"
    assert body["current_level"] == 2

    history = client.get(f"/api/approvals/{approval['id']}/history").json()
    assert len(history) == 2
    assert history[0]["decision"] == "ESCALATED"
    assert history[1]["approver_role"] == "SECURITY"

    finish = client.post(
        f"/api/approvals/{approval['id']}/approve",
        json={"approver_email": "security@example.com"},
    ).json()["approval"]

    assert finish["status"] == "APPROVED"


def test_get_history_not_found(client):

    response = client.get("/api/approvals/999999/history")

    assert response.status_code == 404


# --- Gap: blank/whitespace approver_email must not bypass SoD checks ---


def test_approve_blank_approver_email_rejected(client):

    approval = _create_approval(client)

    response = client.post(
        f"/api/approvals/{approval['id']}/approve",
        json={"approver_email": ""},
    )

    assert response.status_code == 400

    unchanged = client.get(f"/api/approvals/{approval['id']}").json()
    assert unchanged["status"] == "PENDING"


def test_approve_whitespace_approver_email_rejected(client):

    approval = _create_approval(client)

    response = client.post(
        f"/api/approvals/{approval['id']}/approve",
        json={"approver_email": "   "},
    )

    assert response.status_code == 400

    unchanged = client.get(f"/api/approvals/{approval['id']}").json()
    assert unchanged["status"] == "PENDING"


def test_reject_blank_approver_email_rejected(client):

    approval = _create_approval(client)

    response = client.post(
        f"/api/approvals/{approval['id']}/reject",
        json={"approver_email": ""},
    )

    assert response.status_code == 400

    unchanged = client.get(f"/api/approvals/{approval['id']}").json()
    assert unchanged["status"] == "PENDING"


def test_reject_whitespace_approver_email_rejected(client):

    approval = _create_approval(client)

    response = client.post(
        f"/api/approvals/{approval['id']}/reject",
        json={"approver_email": "   "},
    )

    assert response.status_code == 400

    unchanged = client.get(f"/api/approvals/{approval['id']}").json()
    assert unchanged["status"] == "PENDING"


# --- Gap: reject-path separation of duties ---


def test_reject_separation_of_duties_violation(client):

    approval = _create_approval(client, requested_by="same@example.com")

    response = client.post(
        f"/api/approvals/{approval['id']}/reject",
        json={"approver_email": "same@example.com"},
    )

    assert response.status_code == 403

    unchanged = client.get(f"/api/approvals/{approval['id']}").json()
    assert unchanged["status"] == "PENDING"


# --- Gap: escalate on a non-PENDING approval must be a conflict ---


def test_escalate_on_already_approved_is_conflict(client):

    approval = _create_approval(client, required_levels=["MANAGER"])

    client.post(
        f"/api/approvals/{approval['id']}/approve",
        json={"approver_email": "manager@example.com"},
    )

    response = client.post(
        f"/api/approvals/{approval['id']}/escalate",
        json={"approver_email": "manager@example.com", "escalate_to_role": "SECURITY"},
    )

    assert response.status_code == 409


# --- Gap: expires_in_hours override must produce the expected expires_at ---


def test_expires_in_hours_override_sets_expected_expiry(client):

    import datetime

    approval = _create_approval(client, expires_in_hours=5)

    created_at = datetime.datetime.fromisoformat(approval["created_at"])
    expires_at = datetime.datetime.fromisoformat(approval["expires_at"])

    delta_hours = (expires_at - created_at).total_seconds() / 3600.0

    assert abs(delta_hours - 5) < 0.01
