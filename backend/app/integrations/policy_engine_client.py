"""
Integration point for the Identity Policy Engine (Category 4).

This module is NOT a policy engine and must never grow policy rules of
its own. It defines the contract Category 6/7 code depends on, and
forwards calls to a real policy engine implementation if/when one is
added to this codebase at:

    app.services.policy_service.evaluate(operation_type, target_user_id, payload) -> dict

Expected return shape from the real engine:
    {
        "approval_required": bool,
        "required_levels": list[str],   # e.g. ["MANAGER", "SECURITY"]
        "reason": str,
    }

When that module is not present yet, this adapter returns a
conservative safety fallback: it only ever determines that approval
IS required, never that it is safe to skip approval. It does not
attempt to reproduce any real policy logic. Fallback results are
tagged source="ENGINE_UNAVAILABLE" so callers and API responses can
surface this state explicitly rather than presenting it as a genuine
policy decision.

Once Category 4 adds app.services.policy_service, this adapter starts
calling it automatically - no changes are required in any Category
6/7/11 code.
"""

FALLBACK_REQUIRED_LEVELS = ["MANAGER"]


def evaluate_policy(operation_type, target_user_id, payload):

    try:
        from app.services.policy_service import evaluate as _engine_evaluate
    except ImportError:
        return _fallback_decision()

    result = _engine_evaluate(operation_type, target_user_id, payload)
    result.setdefault("source", "ENGINE")

    return result


def _fallback_decision():

    return {
        "approval_required": True,
        "required_levels": FALLBACK_REQUIRED_LEVELS,
        "reason": (
            "Policy Engine unavailable - defaulting to a manual approval "
            "requirement as a safety fallback. This is not a policy "
            "decision produced by a policy engine."
        ),
        "source": "ENGINE_UNAVAILABLE",
    }
