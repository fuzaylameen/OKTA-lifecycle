"""
Integration point for the Identity Impact Analysis engine (Category 7).

This module is NOT an impact engine and must never grow impact analysis
logic of its own. It forwards calls to a real impact engine implementation
if/when one is added to this codebase at:

    app.services.impact_service.evaluate(operation_type, target_user_id, payload) -> dict

Expected return shape from the real engine:
    {
        "impact_level": str,             # e.g. "LOW" / "MEDIUM" / "HIGH"
        "affected_resources": list,      # e.g. groups/apps/entitlements affected
        "reason": str,
    }

When that module is not present yet, this adapter does NOT calculate or
invent an impact assessment. It returns impact_level=None and
affected_resources=None, tagged source="ENGINE_UNAVAILABLE", so callers
can distinguish "no impact data available" from "impact was assessed as
low/none."

Once Category 7 (or a later category) adds app.services.impact_service,
this adapter starts calling it automatically - no changes are required
in any lifecycle execution code.
"""


def evaluate_impact(operation_type, target_user_id, payload):

    try:
        from app.services.impact_service import evaluate as _engine_evaluate
    except ImportError:
        return _fallback_decision()

    result = _engine_evaluate(operation_type, target_user_id, payload)
    result.setdefault("source", "ENGINE")

    return result


def _fallback_decision():

    return {
        "impact_level": None,
        "affected_resources": None,
        "reason": (
            "Impact Engine unavailable - no impact analysis is calculated "
            "or estimated by this fallback."
        ),
        "source": "ENGINE_UNAVAILABLE",
    }
