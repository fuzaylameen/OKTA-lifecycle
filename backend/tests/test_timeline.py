"""
Category 11 - Identity timeline retrieval tests, exercised through
/api/timeline/{user_id} using the TestClient. Drives real dry-run /
confirm / approve flows (through the mocked user_service/group_service)
so that IdentityTimelineEvent and ApprovalStep rows actually exist to
be read back.
"""

from app.services import lifecycle_execution_service


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


def test_timeline_empty_for_unknown_user(client):

    response = client.get("/api/timeline/00uUnknownUser")

    assert response.status_code == 200
    assert response.json() == []


def test_timeline_includes_policy_and_risk_preview_events(
    client, mock_okta_backed_services
):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []

    response = client.post(
        "/api/lifecycle/dry-run",
        json={
            "operation_type": "DEACTIVATE",
            "requested_by": "requester@example.com",
            "target_user_id": "00uTimelineUser",
            "target_user_email": "timeline.user@example.com",
        },
    )
    assert response.status_code == 200

    timeline = client.get("/api/timeline/00uTimelineUser").json()

    event_types = [event["event_type"] for event in timeline]

    assert "POLICY_PREVIEWED" in event_types
    assert "RISK_PREVIEWED" in event_types
    assert all(event["source"] == "TIMELINE_EVENT" for event in timeline)


def test_timeline_includes_approval_and_execution_events(
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

    dry_run = client.post(
        "/api/lifecycle/dry-run",
        json={
            "operation_type": "DEACTIVATE",
            "requested_by": "requester@example.com",
            "target_user_id": "00uFullFlowUser",
            "target_user_email": "full.flow@example.com",
        },
    ).json()["operation"]

    confirmed = client.post(
        f"/api/lifecycle/{dry_run['id']}/confirm"
    ).json()["operation"]

    approval_id = confirmed["approval_request_id"]

    client.post(
        f"/api/approvals/{approval_id}/approve",
        json={"approver_email": "manager@example.com"},
    )

    timeline = client.get("/api/timeline/00uFullFlowUser").json()

    event_types = [event["event_type"] for event in timeline]
    sources = {event["source"] for event in timeline}

    assert "APPROVAL_REQUESTED" in event_types
    assert "OPERATION_EXECUTED" in event_types
    assert "TIMELINE_EVENT" in sources
    assert "APPROVAL_STEP" in sources

    # events must be returned in chronological order
    created_at_values = [event["created_at"] for event in timeline]
    assert created_at_values == sorted(created_at_values)


def test_timeline_category_filter(client, mock_okta_backed_services, monkeypatch):

    user_mock, _ = mock_okta_backed_services
    user_mock.list_users.return_value = []

    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_policy",
        lambda *a, **k: {
            "approval_required": False,
            "required_levels": [],
            "reason": "no approval needed",
            "source": "TEST_OVERRIDE",
        },
    )
    monkeypatch.setattr(
        lifecycle_execution_service, "evaluate_risk",
        lambda *a, **k: NO_RISK_DATA,
    )

    dry_run = client.post(
        "/api/lifecycle/dry-run",
        json={
            "operation_type": "DEACTIVATE",
            "requested_by": "requester@example.com",
            "target_user_id": "00uCategoryUser",
            "target_user_email": "category.user@example.com",
        },
    ).json()["operation"]

    client.post(f"/api/lifecycle/{dry_run['id']}/confirm")

    suspension_events = client.get(
        "/api/timeline/00uCategoryUser", params={"category": "SUSPENSION"}
    ).json()

    policy_events = client.get(
        "/api/timeline/00uCategoryUser", params={"category": "POLICY_DECISION"}
    ).json()

    assert len(suspension_events) >= 1
    assert all(event["category"] == "SUSPENSION" for event in suspension_events)

    assert len(policy_events) >= 1
    assert all(event["category"] == "POLICY_DECISION" for event in policy_events)
