from app.authorization.roles import Role, parse_role, get_role_permissions, get_role_level
from app.authorization.permissions import Permission
from app.authorization.models import AuthContext


def test_role_hierarchy():
    assert get_role_level(Role.VIEWER) < get_role_level(Role.OPERATOR)
    assert get_role_level(Role.OPERATOR) < get_role_level(Role.MANAGER)
    assert get_role_level(Role.MANAGER) < get_role_level(Role.ADMIN)


def test_viewer_permissions():
    viewer_perms = get_role_permissions(Role.VIEWER)
    assert Permission.USER_READ in viewer_perms
    assert Permission.USER_LIST in viewer_perms
    assert Permission.USER_SEARCH in viewer_perms
    assert Permission.AUDIT_READ in viewer_perms

    # Negative checks: Viewer cannot perform any write/mutating actions
    assert Permission.USER_CREATE not in viewer_perms
    assert Permission.USER_UPDATE not in viewer_perms
    assert Permission.USER_ACTIVATE not in viewer_perms
    assert Permission.USER_REACTIVATE not in viewer_perms
    assert Permission.USER_SUSPEND not in viewer_perms
    assert Permission.USER_DEPROVISION not in viewer_perms
    assert Permission.ROLE_MANAGE not in viewer_perms
    assert Permission.POLICY_MANAGE not in viewer_perms


def test_operator_permissions():
    operator_perms = get_role_permissions(Role.OPERATOR)
    assert Permission.USER_READ in operator_perms
    assert Permission.USER_LIST in operator_perms
    assert Permission.USER_SEARCH in operator_perms
    assert Permission.USER_CREATE in operator_perms
    assert Permission.USER_UPDATE in operator_perms
    assert Permission.USER_ACTIVATE in operator_perms
    assert Permission.USER_REACTIVATE in operator_perms

    # Negative checks: Operator cannot suspend, deprovision, or manage roles
    assert Permission.USER_SUSPEND not in operator_perms
    assert Permission.USER_DEPROVISION not in operator_perms
    assert Permission.ROLE_MANAGE not in operator_perms
    assert Permission.POLICY_MANAGE not in operator_perms


def test_manager_permissions():
    manager_perms = get_role_permissions(Role.MANAGER)
    # Includes all Operator permissions
    assert Permission.USER_CREATE in manager_perms
    assert Permission.USER_UPDATE in manager_perms
    assert Permission.USER_ACTIVATE in manager_perms
    assert Permission.USER_REACTIVATE in manager_perms
    # Plus sensitive lifecycle
    assert Permission.USER_SUSPEND in manager_perms
    assert Permission.USER_DEPROVISION in manager_perms

    # Negative checks: Manager cannot manage roles or policies
    assert Permission.ROLE_MANAGE not in manager_perms
    assert Permission.POLICY_MANAGE not in manager_perms


def test_admin_permissions():
    admin_perms = get_role_permissions(Role.ADMIN)
    # Admin has all permissions
    for perm in Permission:
        assert perm in admin_perms


def test_auth_context_permission_checking():
    viewer = AuthContext(user_id="u1", role=Role.VIEWER)
    assert viewer.has_permission(Permission.USER_READ) is True
    assert viewer.has_permission(Permission.USER_CREATE) is False

    operator = AuthContext(user_id="u2", role=Role.OPERATOR)
    assert operator.has_permission(Permission.USER_CREATE) is True
    assert operator.has_permission(Permission.USER_SUSPEND) is False

    manager = AuthContext(user_id="u3", role=Role.MANAGER)
    assert manager.has_permission(Permission.USER_SUSPEND) is True
    assert manager.has_permission(Permission.ROLE_MANAGE) is False

    admin = AuthContext(user_id="u4", role=Role.ADMIN)
    assert admin.has_permission(Permission.ROLE_MANAGE) is True
