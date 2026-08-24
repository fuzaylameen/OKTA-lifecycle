"""
Identity Impact Analysis engine (Category 7 - "Preview access changes").

Computes the access delta (apps/groups gained or lost) for a lifecycle
operation before it is executed, so it can be surfaced in the dry-run
preview alongside the policy and risk decisions.

Called by app.integrations.impact_engine_client.evaluate_impact(), which
is the only consumer of this module - see that module's docstring for
the adapter/fallback contract this module fulfills.

Talks to Okta only through the existing UserService/GroupService (never
OktaClient directly), the same pattern lifecycle_execution_service uses.
"""

from app.services.user_service import UserService
from app.services.group_service import GroupService


user_service = UserService()
group_service = GroupService()


def _app_key(app):

    return app.get("id") if isinstance(app, dict) else None


def _app_label(app):

    return (
        app.get("label")
        or app.get("name")
        or app.get("id")
    ) if isinstance(app, dict) else None


async def _apps_for_group(group_id):

    if not group_id:
        return {}

    apps = await group_service.list_apps(group_id) or []

    return {
        _app_key(app): _app_label(app)
        for app in apps
        if _app_key(app)
    }


async def _apps_for_groups(group_ids):

    combined = {}

    for group_id in group_ids or []:
        combined.update(await _apps_for_group(group_id))

    return combined


async def _groups_for_user(user_id):

    if not user_id:
        return []

    groups = await user_service.list_user_groups(user_id) or []

    return [
        group.get("id")
        for group in groups
        if isinstance(group, dict) and group.get("id")
    ]


def _impact_level(affected_resources):

    count = len(affected_resources)

    if count == 0:
        return "LOW"

    if count <= 2:
        return "MEDIUM"

    return "HIGH"


def _resources(apps, change):

    return [
        {"app_id": app_id, "app_name": app_name, "change": change}
        for app_id, app_name in apps.items()
    ]


def _decision(affected_resources, groups_added, groups_removed, reason):

    return {
        "impact_level": _impact_level(affected_resources),
        "affected_resources": affected_resources,
        "reason": reason,
        "groups_added": groups_added,
        "groups_removed": groups_removed,
    }


async def _evaluate_group_move(payload):

    old_group_id = payload.get("old_group_id")
    new_group_id = payload.get("new_group_id")

    old_apps = await _apps_for_group(old_group_id)
    new_apps = await _apps_for_group(new_group_id)

    apps_lost = {
        app_id: label
        for app_id, label in old_apps.items()
        if app_id not in new_apps
    }
    apps_gained = {
        app_id: label
        for app_id, label in new_apps.items()
        if app_id not in old_apps
    }

    affected_resources = (
        _resources(apps_lost, "LOST") + _resources(apps_gained, "GAINED")
    )

    return _decision(
        affected_resources,
        groups_added=[new_group_id] if new_group_id else [],
        groups_removed=[old_group_id] if old_group_id else [],
        reason=(
            f"Moving from group {old_group_id} to {new_group_id}: "
            f"{len(apps_gained)} app(s) gained, {len(apps_lost)} app(s) lost."
        ),
    )


async def _evaluate_access_removal(target_user_ids, description):

    groups_removed = set()

    for user_id in target_user_ids:
        groups_removed.update(await _groups_for_user(user_id))

    apps_lost = await _apps_for_groups(groups_removed)
    affected_resources = _resources(apps_lost, "LOST")

    return _decision(
        affected_resources,
        groups_added=[],
        groups_removed=sorted(groups_removed),
        reason=(
            f"{description}: access to {len(apps_lost)} app(s) via "
            f"{len(groups_removed)} group(s) will be removed."
        ),
    )


async def _evaluate_access_grant(payload, description):

    group_ids = payload.get("group_ids") or []

    apps_gained = await _apps_for_groups(group_ids)
    affected_resources = _resources(apps_gained, "GAINED")

    return _decision(
        affected_resources,
        groups_added=list(group_ids),
        groups_removed=[],
        reason=(
            f"{description}: access to {len(apps_gained)} app(s) via "
            f"{len(group_ids)} group(s) will be gained."
            if group_ids else
            f"{description}: no group assignments in payload, no access change."
        ),
    )


async def evaluate(operation_type, target_user_id, payload):

    payload = payload or {}

    if operation_type == "GROUP_MOVE":
        return await _evaluate_group_move(payload)

    if operation_type in ("DEACTIVATE", "DELETE"):
        return await _evaluate_access_removal(
            [target_user_id] if target_user_id else [],
            description=f"{operation_type.title()} user",
        )

    if operation_type == "BULK_DEACTIVATE":
        return await _evaluate_access_removal(
            payload.get("user_ids", []),
            description="Bulk deactivate users",
        )

    if operation_type in ("CREATE", "PROVISION"):
        return await _evaluate_access_grant(
            payload,
            description=f"{operation_type.title()} user",
        )

    return _decision(
        [],
        groups_added=[],
        groups_removed=[],
        reason=f"No access preview logic defined for {operation_type}.",
    )
