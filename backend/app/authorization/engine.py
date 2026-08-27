from typing import List
from app.authorization.models import PolicyContext, PolicyDecision
from app.authorization.policies import (
    BasePolicy,
    PreventSelfDeprovisionPolicy,
    ManagerCannotModifyAdminPolicy,
    ManagerCannotDeprovisionManagerOrAdminPolicy,
    SuspensionRequiresReasonPolicy,
    PreventPrivilegeEscalationPolicy,
    PreventSelfRoleEscalationPolicy,
    PrivilegedUserProtectionPolicy,
    ProtectedIdentityGroupPolicy,
)


class PolicyEngine:
    """
    Extensible Policy Engine that evaluates contextual authorization rules.
    """

    def __init__(self, policies: List[BasePolicy] = None):
        self.policies: List[BasePolicy] = policies or []

    def register_policy(self, policy: BasePolicy) -> None:
        self.policies.append(policy)

    def evaluate(self, context: PolicyContext) -> PolicyDecision:
        """
        Evaluate all registered policies against the request context.
        Returns the first denial or allows if all policies pass.
        """
        for policy in self.policies:
            decision = policy.evaluate(context)
            if not decision.allowed:
                return decision
        return PolicyDecision.allow()


def create_default_policy_engine() -> PolicyEngine:
    """
    Instantiate the default PolicyEngine with all standard safety policies (1–8).
    """
    engine = PolicyEngine([
        PreventSelfDeprovisionPolicy(),
        ManagerCannotModifyAdminPolicy(),
        ManagerCannotDeprovisionManagerOrAdminPolicy(),
        SuspensionRequiresReasonPolicy(),
        PreventPrivilegeEscalationPolicy(),
        PreventSelfRoleEscalationPolicy(),
        PrivilegedUserProtectionPolicy(),
        ProtectedIdentityGroupPolicy(),
    ])
    return engine


# Shared default policy engine instance
policy_engine = create_default_policy_engine()

