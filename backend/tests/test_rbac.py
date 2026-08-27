from app.authorization.roles import (
    Role,
    parse_role,
    get_role_permissions,
    get_role_level,
    resolve_role_from_okta_groups,
)
from app.authorization.permissions import Permission
from app.authorization.models import AuthContext
import pytest


def test_role_hierarchy():
    assert get_role_level(Role.AUDITOR) < get_role_level(Role.MANAGER)
    assert get_role_level(Role.MANAGER) < get_role_level(Role.ADMIN)
    assert get_role_level(Role.ADMIN) < get_role_level(Role.ROLE_MANAGER)


def test_auditor_permissions():
    auditor_perms = get_role_permissions(Role.AUDITOR)
    assert Permission.USER_READ in auditor_perms
    assert Permission.USER_LIST in auditor_perms
    assert Permission.USER_SEARCH in auditor_perms
    assert Permission.AUDIT_READ in auditor_perms

    # Negative checks: Auditor cannot perform any lifecycle mutation or role management
    assert Permission.USER_CREATE not in auditor_perms
    assert Permission.USER_UPDATE not in auditor_perms
    assert Permission.USER_ACTIVATE not in auditor_perms
    assert Permission.USER_REACTIVATE not in auditor_perms
    assert Permission.USER_SUSPEND not in auditor_perms
    assert Permission.USER_DEPROVISION not in auditor_perms
    assert Permission.ROLE_MANAGE not in auditor_perms
    assert Permission.POLICY_MANAGE not in auditor_perms


def test_manager_permissions():
    manager_perms = get_role_permissions(Role.MANAGER)
    # Lifecycle permissions
    assert Permission.USER_CREATE in manager_perms
    assert Permission.USER_UPDATE in manager_perms
    assert Permission.USER_ACTIVATE in manager_perms
    assert Permission.USER_REACTIVATE in manager_perms
    assert Permission.USER_SUSPEND in manager_perms
    assert Permission.USER_DEPROVISION in manager_perms
    assert Permission.AUDIT_READ in manager_perms

    # Negative checks: Manager CANNOT manage roles or policies
    assert Permission.ROLE_MANAGE not in manager_perms
    assert Permission.POLICY_MANAGE not in manager_perms


def test_admin_permissions():
    admin_perms = get_role_permissions(Role.ADMIN)
    # Admin has all user lifecycle permissions
    assert Permission.USER_READ in admin_perms
    assert Permission.USER_LIST in admin_perms
    assert Permission.USER_SEARCH in admin_perms
    assert Permission.USER_CREATE in admin_perms
    assert Permission.USER_UPDATE in admin_perms
    assert Permission.USER_ACTIVATE in admin_perms
    assert Permission.USER_REACTIVATE in admin_perms
    assert Permission.USER_SUSPEND in admin_perms
    assert Permission.USER_DEPROVISION in admin_perms
    assert Permission.AUDIT_READ in admin_perms

    # Requirement: Admin can NOT manage roles (role separation)
    assert Permission.ROLE_MANAGE not in admin_perms
    assert Permission.POLICY_MANAGE not in admin_perms


def test_role_manager_permissions():
    rm_perms = get_role_permissions(Role.ROLE_MANAGER)
    # RoleManager has role governance
    assert Permission.ROLE_MANAGE in rm_perms
    assert Permission.POLICY_MANAGE in rm_perms
    assert Permission.AUDIT_READ in rm_perms

    # RoleManager CANNOT perform user lifecycle actions
    assert Permission.USER_CREATE not in rm_perms
    assert Permission.USER_UPDATE not in rm_perms
    assert Permission.USER_ACTIVATE not in rm_perms
    assert Permission.USER_REACTIVATE not in rm_perms
    assert Permission.USER_SUSPEND not in rm_perms
    assert Permission.USER_DEPROVISION not in rm_perms


def test_okta_group_to_role_resolution():
    assert resolve_role_from_okta_groups(["Identity-Auditors"]) == Role.AUDITOR
    assert resolve_role_from_okta_groups(["Identity-Managers"]) == Role.MANAGER
    assert resolve_role_from_okta_groups(["Identity-Admin"]) == Role.ADMIN
    assert resolve_role_from_okta_groups(["Identity-Role-Managers"]) == Role.ROLE_MANAGER

    # Separation of Duties (SoD): User in multiple privileged groups is strictly REJECTED
    with pytest.raises(ValueError) as exc_sod1:
        resolve_role_from_okta_groups(["Identity-Auditors", "Identity-Admin"])
    assert "Separation of Duties violation" in str(exc_sod1.value)

    with pytest.raises(ValueError) as exc_sod2:
        resolve_role_from_okta_groups(["Identity-Managers", "Identity-Role-Managers"])
    assert "Separation of Duties violation" in str(exc_sod2.value)

    # Unauthorized group raises ValueError
    with pytest.raises(ValueError):
        resolve_role_from_okta_groups(["Engineering", "Sales"])



def test_auth_context_permission_checking():
    auditor = AuthContext(user_id="u1", role=Role.AUDITOR)
    assert auditor.has_permission(Permission.USER_READ) is True
    assert auditor.has_permission(Permission.USER_CREATE) is False

    manager = AuthContext(user_id="u2", role=Role.MANAGER)
    assert manager.has_permission(Permission.USER_SUSPEND) is True
    assert manager.has_permission(Permission.ROLE_MANAGE) is False

    admin = AuthContext(user_id="u3", role=Role.ADMIN)
    assert admin.has_permission(Permission.USER_DEPROVISION) is True
    assert admin.has_permission(Permission.ROLE_MANAGE) is False

    role_mgr = AuthContext(user_id="u4", role=Role.ROLE_MANAGER)
    assert role_mgr.has_permission(Permission.ROLE_MANAGE) is True
    assert role_mgr.has_permission(Permission.USER_SUSPEND) is False

