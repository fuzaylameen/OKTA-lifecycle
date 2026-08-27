from enum import Enum
from typing import Set, Dict, List
from app.authorization.permissions import Permission


class Role(str, Enum):
    AUDITOR = "Auditor"
    MANAGER = "Manager"
    ADMIN = "Admin"
    ROLE_MANAGER = "RoleManager"
    # Backward-compatible alias
    VIEWER = "Auditor"
    OPERATOR = "Manager"


ROLE_HIERARCHY: Dict[Role, int] = {
    Role.AUDITOR: 1,
    Role.MANAGER: 2,
    Role.ADMIN: 3,
    Role.ROLE_MANAGER: 4
}

# Mapping from Okta Group Name (lowercased) to Application Role (supports singular & plural)
OKTA_GROUP_ROLE_MAP: Dict[str, Role] = {
    "identity-auditors": Role.AUDITOR,
    "identity-auditor": Role.AUDITOR,
    "identity-managers": Role.MANAGER,
    "identity-manager": Role.MANAGER,
    "identity-admin": Role.ADMIN,
    "identity-admins": Role.ADMIN,
    "identity-role-managers": Role.ROLE_MANAGER,
    "identity-role-manager": Role.ROLE_MANAGER,
}


ROLE_PRECEDENCE: List[Role] = [
    Role.ROLE_MANAGER,
    Role.ADMIN,
    Role.MANAGER,
    Role.AUDITOR,
]

ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    # Auditor: Read-only lifecycle and audit viewing
    Role.AUDITOR: {
        Permission.USER_READ,
        Permission.USER_LIST,
        Permission.USER_SEARCH,
        Permission.AUDIT_READ,
    },
    # Manager: Full user lifecycle operations (No role management)
    Role.MANAGER: {
        Permission.USER_READ,
        Permission.USER_LIST,
        Permission.USER_SEARCH,
        Permission.USER_CREATE,
        Permission.USER_UPDATE,
        Permission.USER_ACTIVATE,
        Permission.USER_REACTIVATE,
        Permission.USER_SUSPEND,
        Permission.USER_DEPROVISION,
        Permission.AUDIT_READ,
    },
    # Admin: Full user lifecycle operations (No role management)
    Role.ADMIN: {
        Permission.USER_READ,
        Permission.USER_LIST,
        Permission.USER_SEARCH,
        Permission.USER_CREATE,
        Permission.USER_UPDATE,
        Permission.USER_ACTIVATE,
        Permission.USER_REACTIVATE,
        Permission.USER_SUSPEND,
        Permission.USER_DEPROVISION,
        Permission.AUDIT_READ,
    },
    # RoleManager: Dedicated role governance only (Strictly NO user lifecycle operations)
    Role.ROLE_MANAGER: {
        Permission.ROLE_MANAGE,
        Permission.POLICY_MANAGE,
        Permission.AUDIT_READ,
        Permission.USER_READ,
        Permission.USER_LIST,
        Permission.USER_SEARCH,
        Permission.AUDIT_READ
    },
}


def parse_role(role_str: str) -> Role:
    """Normalize string to Role enum (case-insensitive lookup with legacy alias support)."""
    if not role_str:
        raise ValueError("Role cannot be empty")
    cleaned = role_str.strip().lower()
    if cleaned in ("viewer", "auditor"):
        return Role.AUDITOR
    if cleaned in ("operator", "manager"):
        return Role.MANAGER
    if cleaned == "admin":
        return Role.ADMIN
    if cleaned in ("rolemanager", "role_manager", "role-manager", "role manager", "identity-role-managers"):
        return Role.ROLE_MANAGER

    for r in (Role.AUDITOR, Role.MANAGER, Role.ADMIN, Role.ROLE_MANAGER):
        if r.value.lower() == cleaned:
            return r
    raise ValueError(f"Unknown role: {role_str}")


def get_role_permissions(role: Role) -> Set[Permission]:
    """Return all permissions granted to a given role."""
    return ROLE_PERMISSIONS.get(role, set())


def get_role_level(role: Role) -> int:
    """Return numeric hierarchy level of a role."""
    return ROLE_HIERARCHY.get(role, 0)


def resolve_role_from_okta_groups(group_names: List[str]) -> Role:
    """
    Map a list of Okta group names to the authorized backend Role.
    Enforces strict Separation of Duties (SoD):
    - If user has 0 privileged groups: raises ValueError (unauthorized).
    - If user has > 1 privileged groups: raises ValueError (SoD violation - cannot hold multiple privileged roles).
    - If user has exactly 1 privileged group: returns the mapped Role.
    """
    matched_groups: List[str] = []
    matched_roles: Set[Role] = set()

    for name in group_names:
        normalized = name.strip().lower()
        if normalized in OKTA_GROUP_ROLE_MAP:
            matched_groups.append(name)
            matched_roles.add(OKTA_GROUP_ROLE_MAP[normalized])

    if not matched_roles:
        raise ValueError("User is not a member of any authorized Identity group")

    # Strict Separation of Duties (SoD) enforcement
    if len(matched_roles) > 1:
        raise ValueError(
            f"Separation of Duties violation: User belongs to multiple privileged Identity groups {matched_groups}. "
            f"A single user is strictly forbidden from belonging to multiple privileged groups simultaneously."
        )

    return list(matched_roles)[0]


