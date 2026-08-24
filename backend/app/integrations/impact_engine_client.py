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

If the module is present but a live Okta call it makes fails (e.g. Okta
is unreachable or returns an error status), this adapter does not let
that exception propagate into the dry-run flow either. It catches
httpx.HTTPError specifically - not exceptions in general, so a genuine
bug in the engine still surfaces instead of being misreported as an
Okta outage - and returns the same impact_level=None/
affected_resources=None shape, tagged source="ENGINE_ERROR" so callers
can distinguish "engine not installed" from "engine installed but this
call failed."

Once Category 7 (or a later category) adds app.services.impact_service,
this adapter starts calling it automatically - no changes are required
in any lifecycle execution code.

The real engine's evaluate() computes access changes by reading group/app
assignments from Okta, so it is a coroutine function. This adapter is
therefore async and awaits it; a plain (synchronous) evaluate() returning
a dict directly is also supported.
"""

import inspect

import httpx


async def evaluate_impact(operation_type, target_user_id, payload):

    try:
        from app.services.impact_service import evaluate as _engine_evaluate
    except ImportError:
        return _fallback_decision()

    try:
        result = _engine_evaluate(operation_type, target_user_id, payload)

        if inspect.isawaitable(result):
            result = await result

    except httpx.HTTPError as exc:
        return _fallback_decision(
            source="ENGINE_ERROR",
            reason=f"Impact Engine call to Okta failed: {exc}",
        )

    result.setdefault("source", "ENGINE")

    return result


def _fallback_decision(source="ENGINE_UNAVAILABLE", reason=None):

    return {
        "impact_level": None,
        "affected_resources": None,
        "reason": reason or (
            "Impact Engine unavailable - no impact analysis is calculated "
            "or estimated by this fallback."
        ),
        "source": source,
    }
