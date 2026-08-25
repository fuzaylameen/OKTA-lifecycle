from app.authorization.roles import Role
from app.authorization.models import AuthContext, PolicyContext
from app.authorization.engine import policy_engine


def test_policy_1_prevent_self_deprovision():
    # Admin attempting to deprovision themselves
    admin = AuthContext(user_id="admin_1", role=Role.ADMIN)
    context_self = PolicyContext(
        requester=admin,
        action="deprovision",
        target_id="admin_1"
    )
    decision = policy_engine.evaluate(context_self)
    assert decision.allowed is False
    assert decision.policy_name == "prevent_self_deprovision"
    assert "Self-deprovisioning is strictly prohibited" in decision.reason

    # Admin deprovisioning another normal user -> ALLOW
    context_other = PolicyContext(
        requester=admin,
        action="deprovision",
        target_id="user_2",
        target_role=Role.OPERATOR
    )
    decision_other = policy_engine.evaluate(context_other)
    assert decision_other.allowed is True


def test_policy_2_manager_cannot_modify_admin():
    manager = AuthContext(user_id="mgr_1", role=Role.MANAGER)

    # Manager attempting to suspend Admin
    context_suspend_admin = PolicyContext(
        requester=manager,
        action="suspend",
        target_id="admin_1",
        target_role=Role.ADMIN,
        reason="Test suspension"
    )
    decision = policy_engine.evaluate(context_suspend_admin)
    assert decision.allowed is False
    assert "Manager" in decision.reason and "Admin" in decision.reason

    # Manager attempting to update Admin
    context_update_admin = PolicyContext(
        requester=manager,
        action="update",
        target_id="admin_1",
        target_role=Role.ADMIN
    )
    decision = policy_engine.evaluate(context_update_admin)
    assert decision.allowed is False


def test_policy_3_manager_cannot_deprovision_manager_or_admin():
    manager = AuthContext(user_id="mgr_1", role=Role.MANAGER)

    # Manager -> Manager deprovision -> DENY
    context_mgr_mgr = PolicyContext(
        requester=manager,
        action="deprovision",
        target_id="mgr_2",
        target_role=Role.MANAGER
    )
    decision = policy_engine.evaluate(context_mgr_mgr)
    assert decision.allowed is False

    # Manager -> Admin deprovision -> DENY
    context_mgr_admin = PolicyContext(
        requester=manager,
        action="deprovision",
        target_id="admin_1",
        target_role=Role.ADMIN
    )
    decision = policy_engine.evaluate(context_mgr_admin)
    assert decision.allowed is False

    # Manager -> Operator deprovision -> ALLOW
    context_mgr_op = PolicyContext(
        requester=manager,
        action="deprovision",
        target_id="op_1",
        target_role=Role.OPERATOR
    )
    decision = policy_engine.evaluate(context_mgr_op)
    assert decision.allowed is True

    # Manager -> Viewer deprovision -> ALLOW
    context_mgr_vw = PolicyContext(
        requester=manager,
        action="deprovision",
        target_id="vw_1",
        target_role=Role.VIEWER
    )
    decision = policy_engine.evaluate(context_mgr_vw)
    assert decision.allowed is True


def test_policy_4_suspension_requires_reason():
    manager = AuthContext(user_id="mgr_1", role=Role.MANAGER)

    # Suspend without reason -> DENY
    context_no_reason = PolicyContext(
        requester=manager,
        action="suspend",
        target_id="user_1",
        target_role=Role.OPERATOR,
        reason=""
    )
    decision = policy_engine.evaluate(context_no_reason)
    assert decision.allowed is False
    assert decision.policy_name == "suspension_requires_reason"
    assert "requires a non-empty reason" in decision.reason

    # Suspend with whitespace only -> DENY
    context_whitespace = PolicyContext(
        requester=manager,
        action="suspend",
        target_id="user_1",
        target_role=Role.OPERATOR,
        reason="   "
    )
    decision = policy_engine.evaluate(context_whitespace)
    assert decision.allowed is False

    # Suspend with valid reason -> ALLOW
    context_with_reason = PolicyContext(
        requester=manager,
        action="suspend",
        target_id="user_1",
        target_role=Role.OPERATOR,
        reason="Security violation investigation"
    )
    decision = policy_engine.evaluate(context_with_reason)
    assert decision.allowed is True


def test_policy_5_prevent_privilege_escalation():
    manager = AuthContext(user_id="mgr_1", role=Role.MANAGER)

    # Manager attempting to promote user to Admin -> DENY
    context_promote = PolicyContext(
        requester=manager,
        action="role_manage",
        target_id="user_1",
        target_role=Role.OPERATOR,
        new_role=Role.ADMIN
    )
    decision = policy_engine.evaluate(context_promote)
    assert decision.allowed is False
    assert decision.policy_name == "prevent_privilege_escalation"

    # Admin assigning Admin role -> ALLOW
    admin = AuthContext(user_id="admin_1", role=Role.ADMIN)
    context_admin_assign = PolicyContext(
        requester=admin,
        action="role_manage",
        target_id="user_1",
        target_role=Role.OPERATOR,
        new_role=Role.ADMIN
    )
    decision = policy_engine.evaluate(context_admin_assign)
    assert decision.allowed is True


def test_policy_6_prevent_self_role_escalation():
    manager = AuthContext(user_id="mgr_1", role=Role.MANAGER)

    # Manager attempting to promote self to Admin -> DENY
    context_self_promote = PolicyContext(
        requester=manager,
        action="role_manage",
        target_id="mgr_1",
        target_role=Role.MANAGER,
        new_role=Role.ADMIN
    )
    decision = policy_engine.evaluate(context_self_promote)
    assert decision.allowed is False
    assert "Self-role escalation" in decision.reason or "exceeds" in decision.reason


def test_policy_7_privileged_user_protection():
    # Manager modifying Manager
    manager = AuthContext(user_id="mgr_1", role=Role.MANAGER)
    context_mgr_mgr = PolicyContext(
        requester=manager,
        action="suspend",
        target_id="mgr_2",
        target_role=Role.MANAGER,
        reason="Disciplinary reason"
    )
    decision = policy_engine.evaluate(context_mgr_mgr)
    assert decision.allowed is False

    # Admin modifying normal user -> ALLOW
    admin = AuthContext(user_id="admin_1", role=Role.ADMIN)
    context_admin_op = PolicyContext(
        requester=admin,
        action="suspend",
        target_id="op_1",
        target_role=Role.OPERATOR,
        reason="Normal administrative suspension"
    )
    decision = policy_engine.evaluate(context_admin_op)
    assert decision.allowed is True
