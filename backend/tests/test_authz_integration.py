import time
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import jwt

from app.main import app
from app.core.config import settings
from app.auth.jwt_handler import create_user_token
from app.services.okta_client import OktaClient


client = TestClient(app)


def get_auth_headers(user_id: str, email: str, role: str):
    token = create_user_token(user_id=user_id, email=email, role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def mock_okta_request():
    """Mock okta_client.OktaClient.request so no live Okta calls are made during tests."""
    with patch.object(OktaClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {
            "id": "mock_okta_usr_123",
            "status": "ACTIVE",
            "profile": {
                "firstName": "John",
                "lastName": "Doe",
                "email": "john.doe@example.com",
                "login": "john.doe@example.com"
            }
        }
        yield mock_req


# ==============================================================================
# SCENARIO TESTS REQUIRED BY SPECIFICATION
# ==============================================================================

def test_viewer_get_users_allowed(mock_okta_request):
    """Scenario 1: Viewer -> GET user -> ALLOW (200)"""
    headers = get_auth_headers("vw_1", "viewer@company.com", "Viewer")
    response = client.get("/api/users/", headers=headers)
    assert response.status_code == 200
    assert mock_okta_request.called is True


def test_viewer_create_user_denied(mock_okta_request):
    """Scenario 2: Viewer -> CREATE user -> DENY (403) and Okta never reached"""
    headers = get_auth_headers("vw_1", "viewer@company.com", "Viewer")
    response = client.post(
        "/api/users/",
        json={"first_name": "New", "last_name": "User", "email": "new@example.com"},
        headers=headers
    )
    assert response.status_code == 403
    assert "user:create" in response.json()["detail"]
    assert mock_okta_request.called is False  # CRITICAL: Okta never reached


def test_operator_create_user_allowed(mock_okta_request):
    """Scenario 3: Operator -> CREATE user -> ALLOW (200)"""
    headers = get_auth_headers("op_1", "operator@company.com", "Operator")
    response = client.post(
        "/api/users/",
        json={"first_name": "Jane", "last_name": "Smith", "email": "jane@example.com"},
        headers=headers
    )
    assert response.status_code == 200
    assert mock_okta_request.called is True


def test_operator_suspend_user_denied(mock_okta_request):
    """Scenario 4: Operator -> SUSPEND user -> DENY (403)"""
    headers = get_auth_headers("op_1", "operator@company.com", "Operator")
    response = client.post(
        "/api/users/target_123/suspend",
        json={"reason": "Security violation"},
        headers=headers
    )
    assert response.status_code == 403
    assert "user:suspend" in response.json()["detail"]
    assert mock_okta_request.called is False


def test_manager_suspend_normal_user_allowed(mock_okta_request):
    """Scenario 5: Manager -> SUSPEND normal user with reason -> ALLOW (200)"""
    headers = get_auth_headers("mgr_1", "manager@company.com", "Manager")
    headers["X-Target-Role"] = "Operator"
    response = client.post(
        "/api/users/target_op_123/suspend",
        json={"reason": "Disciplinary suspension"},
        headers=headers
    )
    assert response.status_code == 200
    assert mock_okta_request.called is True


def test_manager_suspend_admin_denied(mock_okta_request):
    """Scenario 6: Manager -> SUSPEND Admin -> DENY (403)"""
    headers = get_auth_headers("mgr_1", "manager@company.com", "Manager")
    headers["X-Target-Role"] = "Admin"
    response = client.post(
        "/api/users/admin_user_1/suspend",
        json={"reason": "Attempted admin suspension"},
        headers=headers
    )
    assert response.status_code == 403
    assert "Admin" in response.json()["detail"]
    assert mock_okta_request.called is False


def test_manager_deprovision_operator_allowed(mock_okta_request):
    """Scenario 7: Manager -> DEPROVISION Operator -> ALLOW (200)"""
    headers = get_auth_headers("mgr_1", "manager@company.com", "Manager")
    headers["X-Target-Role"] = "Operator"
    response = client.delete(
        "/api/users/op_123",
        headers=headers
    )
    assert response.status_code == 200
    assert mock_okta_request.called is True


def test_manager_deprovision_manager_denied(mock_okta_request):
    """Scenario 8: Manager -> DEPROVISION Manager -> DENY (403)"""
    headers = get_auth_headers("mgr_1", "manager@company.com", "Manager")
    headers["X-Target-Role"] = "Manager"
    response = client.delete(
        "/api/users/other_mgr_456",
        headers=headers
    )
    assert response.status_code == 403
    assert mock_okta_request.called is False


def test_manager_deprovision_admin_denied(mock_okta_request):
    """Scenario 9: Manager -> DEPROVISION Admin -> DENY (403)"""
    headers = get_auth_headers("mgr_1", "manager@company.com", "Manager")
    headers["X-Target-Role"] = "Admin"
    response = client.delete(
        "/api/users/admin_789",
        headers=headers
    )
    assert response.status_code == 403
    assert mock_okta_request.called is False


def test_admin_deprovision_normal_user_allowed(mock_okta_request):
    """Scenario 10: Admin -> DEPROVISION normal user -> ALLOW (200)"""
    headers = get_auth_headers("admin_1", "admin@company.com", "Admin")
    headers["X-Target-Role"] = "Operator"
    response = client.delete(
        "/api/users/target_op_999",
        headers=headers
    )
    assert response.status_code == 200
    assert mock_okta_request.called is True


def test_admin_deprovision_self_denied(mock_okta_request):
    """Scenario 11: Admin -> DEPROVISION self -> DENY (403 - Policy 1)"""
    headers = get_auth_headers("admin_1", "admin@company.com", "Admin")
    response = client.delete(
        "/api/users/admin_1",
        headers=headers
    )
    assert response.status_code == 403
    assert "Self-deprovisioning" in response.json()["detail"]
    assert mock_okta_request.called is False


def test_manager_promote_user_to_admin_denied(mock_okta_request):
    """Scenario 12: Manager -> promote user to Admin -> DENY (403 - missing role:manage)"""
    headers = get_auth_headers("mgr_1", "manager@company.com", "Manager")
    response = client.post(
        "/api/users/user_target_123/role",
        json={"role": "Admin"},
        headers=headers
    )
    assert response.status_code == 403
    assert "role:manage" in response.json()["detail"]
    assert mock_okta_request.called is False


def test_suspend_without_reason_denied(mock_okta_request):
    """Scenario 13: Suspend without reason -> 422 Unprocessable or 403 Policy violation"""
    headers = get_auth_headers("admin_1", "admin@company.com", "Admin")
    # Empty string reason fails Pydantic validation (min_length=1) or Policy 4
    response = client.post(
        "/api/users/target_123/suspend",
        json={"reason": ""},
        headers=headers
    )
    assert response.status_code in {400, 403, 422}
    assert mock_okta_request.called is False


def test_missing_jwt_returns_401(mock_okta_request):
    """Scenario 14: Missing JWT -> 401 Unauthorized"""
    response = client.get("/api/users/")
    assert response.status_code == 401
    assert mock_okta_request.called is False


def test_invalid_jwt_returns_401(mock_okta_request):
    """Scenario 15: Invalid JWT -> 401 Unauthorized"""
    response = client.get("/api/users/", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert response.status_code == 401
    assert mock_okta_request.called is False


def test_expired_jwt_returns_401(mock_okta_request):
    """Scenario 16: Expired JWT -> 401 Unauthorized"""
    now = int(time.time())
    payload = {
        "iss": settings.USER_JWT_ISSUER,
        "aud": settings.USER_JWT_AUDIENCE,
        "sub": "usr_expired",
        "email": "expired@company.com",
        "role": "Admin",
        "iat": now - 3600,
        "exp": now - 10,
    }
    expired_token = jwt.encode(payload, settings.USER_JWT_SECRET, algorithm=settings.USER_JWT_ALGORITHM)
    response = client.get("/api/users/", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
    assert mock_okta_request.called is False


def test_valid_jwt_insufficient_role_returns_403(mock_okta_request):
    """Scenario 17: Valid JWT but insufficient role -> 403 Forbidden"""
    headers = get_auth_headers("vw_1", "viewer@company.com", "Viewer")
    response = client.post(
        "/api/users/user_123/provision",
        headers=headers
    )
    assert response.status_code == 403
    assert mock_okta_request.called is False
