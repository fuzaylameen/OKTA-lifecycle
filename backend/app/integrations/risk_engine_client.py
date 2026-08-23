"""
Integration point for the Identity Risk & Decision Engine (Category 5).

This module is NOT a risk engine and must never grow scoring logic of
its own. It forwards calls to a real risk engine implementation if/when
one is added to this codebase at:

    app.services.risk_service.evaluate(operation_type, target_user_id, payload) -> dict

Expected return shape from the real engine:
    {
        "risk_score": int,      # 0-100
        "risk_band": str,       # e.g. "LOW" / "MEDIUM" / "HIGH"
        "reason": str,
    }

When that module is not present yet, this adapter does NOT calculate
or invent a risk score. It returns risk_score=None and risk_band=None,
tagged source="ENGINE_UNAVAILABLE", so callers can distinguish "no risk
data available" from "risk was assessed as low/zero."

Once Category 5 adds app.services.risk_service, this adapter starts
calling it automatically - no changes are required in any Category
6/7/11 code.
"""


def evaluate_risk(operation_type, target_user_id, payload):

    try:
        from app.services.risk_service import evaluate as _engine_evaluate
    except ImportError:
        return _fallback_decision()

    result = _engine_evaluate(operation_type, target_user_id, payload)
    result.setdefault("source", "ENGINE")

    return result


def _fallback_decision():

    return {
        "risk_score": None,
        "risk_band": None,
        "reason": (
            "Risk Engine unavailable - no risk score is calculated or "
            "estimated by this fallback."
        ),
        "source": "ENGINE_UNAVAILABLE",
    }
