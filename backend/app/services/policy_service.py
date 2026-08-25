"""
Identity Policy Engine (Category 4 - "Preview policy decisions").

Determines whether a lifecycle operation requires approval before it can
be executed, and which approval level(s) are required, using a static
per-operation-type rule table. No Okta/network/database calls - this is
pure, synchronous, in-memory logic by design (see evaluate() below).

Called by app.integrations.policy_engine_client.evaluate_policy(), which
is the only consumer of this module - see that module's docstring for
the adapter/fallback contract this module fulfills.
"""

RULES = {
    # Staged user, no access granted yet - low risk.
    "CREATE": {
        "approval_required": False,
        "required_levels": [],
        "reason": "Creating a staged user grants no access - no approval required.",
    },
    # Activates access for the user - requires manager approval.
    "PROVISION": {
        "approval_required": True,
        "required_levels": ["MANAGER"],
        "reason": "Provisioning activates user access and requires manager approval.",
    },
    # Access change - moderate risk.
    "GROUP_MOVE": {
        "approval_required": True,
        "required_levels": ["MANAGER"],
        "reason": "Group moves change access and require manager approval.",
    },
    # Revokes access - moderate risk.
    "DEACTIVATE": {
        "approval_required": True,
        "required_levels": ["MANAGER"],
        "reason": "Deactivation revokes access and requires manager approval.",
    },
    # Revokes access at scale - higher risk.
    "BULK_DEACTIVATE": {
        "approval_required": True,
        "required_levels": ["MANAGER", "SECURITY"],
        "reason": (
            "Bulk deactivation revokes access at scale and requires "
            "manager and security approval."
        ),
    },
    # Irreversible - higher risk.
    "DELETE": {
        "approval_required": True,
        "required_levels": ["MANAGER", "SECURITY"],
        "reason": "Deletion is irreversible and requires manager and security approval.",
    },
    # Restores access after a prior deactivation - same tier as DEACTIVATE.
    "REACTIVATE": {
        "approval_required": True,
        "required_levels": ["MANAGER"],
        "reason": "Reactivation restores access and requires manager approval.",
    },
    # Does not grant or revoke access - low risk.
    "PROFILE_UPDATE": {
        "approval_required": False,
        "required_levels": [],
        "reason": "Profile updates do not change access - no approval required.",
    },
}

_UNKNOWN_OPERATION_RULE = {
    "approval_required": True,
    "required_levels": ["MANAGER"],
    "reason": "No policy rule defined for this operation type - failing closed.",
}


def evaluate(operation_type, target_user_id, payload):

    rule = RULES.get(operation_type, _UNKNOWN_OPERATION_RULE)

    return {
        "approval_required": rule["approval_required"],
        "required_levels": list(rule["required_levels"]),
        "reason": rule["reason"],
    }
