from abc import ABC, abstractmethod
from typing import Set
from app.authorization.models import PolicyContext, PolicyDecision
from app.authorization.roles import Role, get_role_level

DEPROVISION_ACTIONS: Set[str] = {"deprovision", "delete", "deactivate"}
SENSITIVE_ACTIONS: Set[str] = {"suspend", "deprovision", "delete", "deactivate", "update", "role_manage", "assign_role"}


class BasePolicy(ABC):
    name: str = "BasePolicy"

    @abstractmethod
    def evaluate(self, context: PolicyContext) -> PolicyDecision:
        """
        Evaluate the policy against the given context.
        Returns PolicyDecision.allow() or PolicyDecision.deny(policy_name, reason).
        """
        pass


class PreventSelfDeprovisionPolicy(BasePolicy):
    """
    Policy 1 — Prevent self-deprovisioning
    Even Admin cannot deprovision themselves.
    """
    name = "prevent_self_deprovision"

    def evaluate(self, context: PolicyContext) -> PolicyDecision:
        if context.action in DEPROVISION_ACTIONS and context.target_id:
            if context.requester.user_id == context.target_id:
                return PolicyDecision.deny(
                    self.name,
                    "Self-deprovisioning is strictly prohibited for all users including Admins."
                )
        return PolicyDecision.allow()


class ManagerCannotModifyAdminPolicy(BasePolicy):
    """
    Policy 2 — Manager cannot modify Admin
    Managers cannot perform sensitive operations against Admin accounts.
    """
    name = "manager_cannot_modify_admin"

    def evaluate(self, context: PolicyContext) -> PolicyDecision:
        if (
            context.requester.role == Role.MANAGER
            and context.target_role == Role.ADMIN
            and context.action in SENSITIVE_ACTIONS
        ):
            return PolicyDecision.deny(
                self.name,
                f"Managers are not permitted to perform sensitive action '{context.action}' on Admin accounts."
            )
        return PolicyDecision.allow()


class ManagerCannotDeprovisionManagerOrAdminPolicy(BasePolicy):
    """
    Policy 3 — Manager cannot deprovision Manager/Admin
    Managers may only deprovision lower-privileged users (Viewer, Operator).
    """
    name = "manager_cannot_deprovision_manager_or_admin"

    def evaluate(self, context: PolicyContext) -> PolicyDecision:
        if (
            context.requester.role == Role.MANAGER
            and context.action in DEPROVISION_ACTIONS
            and context.target_role in {Role.MANAGER, Role.ADMIN}
        ):
            return PolicyDecision.deny(
                self.name,
                f"Managers cannot deprovision accounts with '{context.target_role.value}' role."
            )
        return PolicyDecision.allow()


class SuspensionRequiresReasonPolicy(BasePolicy):
    """
    Policy 4 — Suspension requires a reason
    Action == 'suspend' requires a non-empty reason.
    """
    name = "suspension_requires_reason"

    def evaluate(self, context: PolicyContext) -> PolicyDecision:
        if context.action == "suspend":
            if not context.reason or not context.reason.strip():
                return PolicyDecision.deny(
                    self.name,
                    "Suspension requires a non-empty reason explaining the security or administrative justification."
                )
        return PolicyDecision.allow()


class PreventPrivilegeEscalationPolicy(BasePolicy):
    """
    Policy 5 — Prevent privilege escalation
    Requesters cannot assign a role higher than their own privilege level.
    """
    name = "prevent_privilege_escalation"

    def evaluate(self, context: PolicyContext) -> PolicyDecision:
        if context.action in {"role_manage", "assign_role", "role_change"}:
            if context.new_role:
                requester_level = get_role_level(context.requester.role)
                new_role_level = get_role_level(context.new_role)
                if new_role_level > requester_level:
                    return PolicyDecision.deny(
                        self.name,
                        f"Cannot assign role '{context.new_role.value}' which exceeds requester's privilege level '{context.requester.role.value}'."
                    )
        return PolicyDecision.allow()


class PreventSelfRoleEscalationPolicy(BasePolicy):
    """
    Policy 6 — Prevent self-role escalation
    A user cannot change their own role to a higher privilege level.
    """
    name = "prevent_self_role_escalation"

    def evaluate(self, context: PolicyContext) -> PolicyDecision:
        if context.action in {"role_manage", "assign_role", "role_change"}:
            if context.target_id and context.requester.user_id == context.target_id and context.new_role:
                requester_level = get_role_level(context.requester.role)
                new_role_level = get_role_level(context.new_role)
                if new_role_level > requester_level:
                    return PolicyDecision.deny(
                        self.name,
                        f"Self-role escalation from '{context.requester.role.value}' to '{context.new_role.value}' is prohibited."
                    )
        return PolicyDecision.allow()


class PrivilegedUserProtectionPolicy(BasePolicy):
    """
    Policy 7 — Privileged-user protection
    Protects privileged accounts (Manager/Admin/RoleManager) from actions by peers or lower roles.
    """
    name = "privileged_user_protection"

    def evaluate(self, context: PolicyContext) -> PolicyDecision:
        if context.target_role in {Role.MANAGER, Role.ADMIN, Role.ROLE_MANAGER} and context.action in SENSITIVE_ACTIONS:
            requester_level = get_role_level(context.requester.role)
            target_level = get_role_level(context.target_role)

            # Lower-privileged users cannot modify privileged users
            if requester_level < target_level:
                return PolicyDecision.deny(
                    self.name,
                    f"Requester role '{context.requester.role.value}' cannot perform '{context.action}' on privileged role '{context.target_role.value}'."
                )

            # Manager modifying another Manager is not allowed for sensitive operations
            if context.requester.role == Role.MANAGER and context.target_role == Role.MANAGER and context.requester.user_id != context.target_id:
                return PolicyDecision.deny(
                    self.name,
                    "Managers cannot perform sensitive operations on peer Manager accounts."
                )

        return PolicyDecision.allow()


PROTECTED_IDENTITY_GROUPS: Set[str] = {
    "identity-auditors",
    "identity-auditor",
    "identity-managers",
    "identity-manager",
    "identity-admin",
    "identity-admins",
    "identity-role-managers",
    "identity-role-manager",
}



class ProtectedIdentityGroupPolicy(BasePolicy):
    """
    Policy 8 — Protected Identity Group Policy
    Prevents protected Identity groups (Identity-Auditors, Identity-Managers, Identity-Admin,
    Identity-Role-Managers) from being modified through application group management operations.
    """
    name = "protected_identity_group_policy"

    def evaluate(self, context: PolicyContext) -> PolicyDecision:
        if context.action in {"group_manage", "group_modify", "move_user", "group_update", "delete_group", "add_to_group", "remove_from_group"}:
            targets_to_check = []
            if "old_group" in context.attributes and context.attributes["old_group"]:
                targets_to_check.append(str(context.attributes["old_group"]).strip().lower())
            if "new_group" in context.attributes and context.attributes["new_group"]:
                targets_to_check.append(str(context.attributes["new_group"]).strip().lower())
            if "group_name" in context.attributes and context.attributes["group_name"]:
                targets_to_check.append(str(context.attributes["group_name"]).strip().lower())
            if context.target_id:
                targets_to_check.append(str(context.target_id).strip().lower())

            for target in targets_to_check:
                if target in PROTECTED_IDENTITY_GROUPS:
                    return PolicyDecision.deny(
                        self.name,
                        f"Modifications to protected Identity group '{target}' are strictly prohibited for all application roles."
                    )
        return PolicyDecision.allow()

