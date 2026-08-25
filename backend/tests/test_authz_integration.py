import time
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import jwt

from app.main import app
from app.core.config import settings
from app.auth.jwt_handler import create_user_token
from app.services.okta_client import OktaClient
from app.services.user_service import UserService
from app.services.group_service import GroupService


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
# EMAIL-BASED OKTA GROUP TOKEN ISSUANCE TESTS
# ==============================================================================

def test_token_issuance_valid_okta_group_admin():
    """Valid user in Identity-Admin group gets Admin JWT."""
    with patch.object(UserService, "get_user_by_email", new_callable=AsyncMock) as mock_get_user, \
         patch.object(UserService, "get_user_groups", new_callable=AsyncMock) as mock_get_groups:

        mock_get_user.return_value = {
            "id": "okta_admin_01",
            "profile": {"email": "admin@company.com", "firstName": "Alice"}
        }
        mock_get_groups.return_value = [
            {"id": "g1", "profile": {"name": "Identity-Admin"}}
        ]

        response = client.post("/api/auth/token", json={"email": "admin@company.com"})
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "Admin"
        assert data["user_id"] == "okta_admin_01"
        assert "access_token" in data


def test_token_issuance_valid_okta_group_role_manager():
    """Valid user in Identity-Role-Managers group gets RoleManager JWT."""
    with patch.object(UserService, "get_user_by_email", new_callable=AsyncMock) as mock_get_user, \
         patch.object(UserService, "get_user_groups", new_callable=AsyncMock) as mock_get_groups:

        mock_get_user.return_value = {
            "id": "okta_rm_01",
            "profile": {"email": "rm@company.com", "firstName": "Bob"}
        }
        mock_get_groups.return_value = [
            {"id": "g2", "profile": {"name": "Identity-Role-Managers"}}
        ]

        response = client.post("/api/auth/token", json={"email": "rm@company.com"})
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "RoleManager"
        assert data["user_id"] == "okta_rm_01"


def test_token_issuance_user_not_in_okta_rejected():
    """User not found in Okta directory -> 401 Unauthorized."""
    with patch.object(UserService, "get_user_by_email", new_callable=AsyncMock) as mock_get_user:
        mock_get_user.side_effect = Exception("Not found")

        response = client.post("/api/auth/token", json={"email": "nonexistent@company.com"})
        assert response.status_code == 401
        assert "not found in okta directory" in response.json()["detail"].lower()


def test_token_issuance_user_without_authorized_group_rejected():
    """User exists in Okta but belongs to no authorized group -> 403 Forbidden."""
    with patch.object(UserService, "get_user_by_email", new_callable=AsyncMock) as mock_get_user, \
         patch.object(UserService, "get_user_groups", new_callable=AsyncMock) as mock_get_groups:

        mock_get_user.return_value = {
            "id": "okta_sales_01",
            "profile": {"email": "sales@company.com"}
        }
        mock_get_groups.return_value = [
            {"id": "g_sales", "profile": {"name": "Sales-Team"}}
        ]

        response = client.post("/api/auth/token", json={"email": "sales@company.com"})
        assert response.status_code == 403
        assert "not a member of any authorized identity group" in response.json()["detail"].lower()


def test_token_issuance_separation_of_duties_violation_rejected():
    """User belongs to multiple privileged groups (e.g. Admin + RoleManager) -> 403 Forbidden."""
    with patch.object(UserService, "get_user_by_email", new_callable=AsyncMock) as mock_get_user, \
         patch.object(UserService, "get_user_groups", new_callable=AsyncMock) as mock_get_groups:

        mock_get_user.return_value = {
            "id": "okta_dual_01",
            "profile": {"email": "dual@company.com"}
        }
        mock_get_groups.return_value = [
            {"id": "g_admin", "profile": {"name": "Identity-Admin"}},
            {"id": "g_rm", "profile": {"name": "Identity-Role-Managers"}}
        ]

        response = client.post("/api/auth/token", json={"email": "dual@company.com"})
        assert response.status_code == 403
        assert "separation of duties violation" in response.json()["detail"].lower()



# ==============================================================================
# RBAC & POLICY AUTHORIZATION SCENARIO TESTS
# ==============================================================================

def test_auditor_get_users_allowed(mock_okta_request):
    """Auditor -> GET user -> ALLOW (200)"""
    headers = get_auth_headers("aud_1", "auditor@company.com", "Auditor")
    response = client.get("/api/users/", headers=headers)
    assert response.status_code == 200
    assert mock_okta_request.called is True


def test_auditor_create_user_denied(mock_okta_request):
    """Auditor -> CREATE user -> DENY (403) and Okta never reached"""
    headers = get_auth_headers("aud_1", "auditor@company.com", "Auditor")
    response = client.post(
        "/api/users/",
        json={"first_name": "New", "last_name": "User", "email": "new@example.com"},
        headers=headers
    )
    assert response.status_code == 403
    assert "user:create" in response.json()["detail"]
    assert mock_okta_request.called is False  # CRITICAL: Okta never reached


def test_manager_create_user_allowed(mock_okta_request):
    """Manager -> CREATE user -> ALLOW (200)"""
    headers = get_auth_headers("mgr_1", "manager@company.com", "Manager")
    response = client.post(
        "/api/users/",
        json={"first_name": "Jane", "last_name": "Smith", "email": "jane@example.com"},
        headers=headers
    )
    assert response.status_code == 200
    assert mock_okta_request.called is True


def test_manager_suspend_normal_user_allowed(mock_okta_request):
    """Manager -> SUSPEND normal user with reason -> ALLOW (200)"""
    headers = get_auth_headers("mgr_1", "manager@company.com", "Manager")
    with patch.object(UserService, "get_user_groups", new_callable=AsyncMock) as mock_target_groups:
        mock_target_groups.return_value = [{"profile": {"name": "Identity-Auditors"}}]
        response = client.post(
            "/api/users/target_op_123/suspend",
            json={"reason": "Disciplinary suspension"},
            headers=headers
        )
        assert response.status_code == 200
        assert mock_okta_request.called is True


def test_manager_suspend_admin_denied(mock_okta_request):
    """Manager -> SUSPEND Admin -> DENY (403)"""
    headers = get_auth_headers("mgr_1", "manager@company.com", "Manager")
    with patch.object(UserService, "get_user_groups", new_callable=AsyncMock) as mock_target_groups:
        mock_target_groups.return_value = [{"profile": {"name": "Identity-Admin"}}]
        response = client.post(
            "/api/users/admin_user_1/suspend",
            json={"reason": "Attempted admin suspension"},
            headers=headers
        )
        assert response.status_code == 403
        assert "Admin" in response.json()["detail"]
        assert mock_okta_request.called is False


def test_manager_deprovision_auditor_allowed(mock_okta_request):
    """Manager -> DEPROVISION Auditor -> ALLOW (200)"""
    headers = get_auth_headers("mgr_1", "manager@company.com", "Manager")
    with patch.object(UserService, "get_user_groups", new_callable=AsyncMock) as mock_target_groups:
        mock_target_groups.return_value = [{"profile": {"name": "Identity-Auditors"}}]
        response = client.delete(
            "/api/users/aud_123",
            headers=headers
        )
        assert response.status_code == 200
        assert mock_okta_request.called is True



def test_admin_deprovision_self_denied(mock_okta_request):
    """Admin -> DEPROVISION self -> DENY (403 - Policy 1)"""
    headers = get_auth_headers("admin_1", "admin@company.com", "Admin")
    response = client.delete(
        "/api/users/admin_1",
        headers=headers
    )
    assert response.status_code == 403
    assert "Self-deprovisioning" in response.json()["detail"]
    assert mock_okta_request.called is False


# ==============================================================================
# ROLE SEPARATION TESTS (RoleManager vs Lifecycle Roles)
# ==============================================================================

def test_admin_assign_role_denied(mock_okta_request):
    """Admin -> assign role -> DENY (403: Admin cannot manage roles)"""
    headers = get_auth_headers("admin_1", "admin@company.com", "Admin")
    response = client.post(
        "/api/users/target_user_123/role",
        json={"role": "Manager"},
        headers=headers
    )
    assert response.status_code == 403
    assert "role:manage" in response.json()["detail"]
    assert mock_okta_request.called is False


def test_manager_assign_role_denied(mock_okta_request):
    """Manager -> assign role -> DENY (403: Manager cannot manage roles)"""
    headers = get_auth_headers("mgr_1", "manager@company.com", "Manager")
    response = client.post(
        "/api/users/target_user_123/role",
        json={"role": "Auditor"},
        headers=headers
    )
    assert response.status_code == 403
    assert "role:manage" in response.json()["detail"]
    assert mock_okta_request.called is False


def test_role_manager_assign_role_allowed(mock_okta_request):
    """RoleManager -> assign role -> ALLOW (200)"""
    headers = get_auth_headers("rm_1", "rm@company.com", "RoleManager")
    response = client.post(
        "/api/users/target_user_123/role",
        json={"role": "Manager"},
        headers=headers
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_role_manager_lifecycle_create_user_denied(mock_okta_request):
    """RoleManager -> create user -> DENY (403: RoleManager has NO lifecycle access)"""
    headers = get_auth_headers("rm_1", "rm@company.com", "RoleManager")
    response = client.post(
        "/api/users/",
        json={"first_name": "Test", "last_name": "User", "email": "test@company.com"},
        headers=headers
    )
    assert response.status_code == 403
    assert "user:create" in response.json()["detail"]
    assert mock_okta_request.called is False


def test_role_manager_lifecycle_suspend_user_denied(mock_okta_request):
    """RoleManager -> suspend user -> DENY (403: RoleManager has NO lifecycle access)"""
    headers = get_auth_headers("rm_1", "rm@company.com", "RoleManager")
    response = client.post(
        "/api/users/target_123/suspend",
        json={"reason": "Attempted suspension"},
        headers=headers
    )
    assert response.status_code == 403
    assert "user:suspend" in response.json()["detail"]
    assert mock_okta_request.called is False


# ==============================================================================
# PROTECTED IDENTITY GROUP POLICY TESTS
# ==============================================================================

def test_modify_protected_identity_group_denied(mock_okta_request):
    """Moving user into Identity-Admin or Identity-Managers -> DENY (403: Policy 8)"""
    headers = get_auth_headers("mgr_1", "manager@company.com", "Manager")
    response = client.post(
        "/api/groups/move",
        json={
            "user_id": "u1",
            "old_group_id": "General-Staff",
            "new_group_id": "Identity-Admin"
        },
        headers=headers
    )
    assert response.status_code == 403
    assert "protected identity group" in response.json()["detail"].lower()
    assert mock_okta_request.called is False


def test_modify_normal_group_allowed(mock_okta_request):
    """Moving user between non-protected normal groups -> ALLOW (200)"""
    headers = get_auth_headers("mgr_1", "manager@company.com", "Manager")
    with patch.object(GroupService, "list_groups", new_callable=AsyncMock) as mock_list_groups, \
         patch.object(GroupService, "move_user", new_callable=AsyncMock) as mock_move:
        mock_list_groups.return_value = [
            {"id": "g_sales", "profile": {"name": "Sales"}},
            {"id": "g_eng", "profile": {"name": "Engineering"}}
        ]
        mock_move.return_value = {"user_id": "u1", "old_group": "g_sales", "new_group": "g_eng"}

        response = client.post(
            "/api/groups/move",
            json={
                "user_id": "u1",
                "old_group_id": "g_sales",
                "new_group_id": "g_eng"
            },
            headers=headers
        )
        assert response.status_code == 200
        assert response.json()["success"] is True


# ==============================================================================
# JWT VALIDATION ERROR TESTS
# ==============================================================================

def test_missing_jwt_returns_401(mock_okta_request):
    response = client.get("/api/users/")
    assert response.status_code == 401
    assert mock_okta_request.called is False


def test_invalid_jwt_returns_401(mock_okta_request):
    response = client.get("/api/users/", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert response.status_code == 401
    assert mock_okta_request.called is False


def test_expired_jwt_returns_401(mock_okta_request):
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

