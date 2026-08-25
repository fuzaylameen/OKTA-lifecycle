from enum import Enum
from typing import Set, Dict
from app.authorization.permissions import Permission


class Role(str, Enum):
    VIEWER = "Viewer"
    OPERATOR = "Operator"
    MANAGER = "Manager"
    ADMIN = "Admin"


ROLE_HIERARCHY: Dict[Role, int] = {
    Role.VIEWER: 1,
    Role.OPERATOR: 2,
    Role.MANAGER: 3,
    Role.ADMIN: 4,
}

ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.VIEWER: {
        Permission.USER_READ,
        Permission.USER_LIST,
        Permission.USER_SEARCH,
        Permission.AUDIT_READ,
    },
    Role.OPERATOR: {
        Permission.USER_READ,
        Permission.USER_LIST,
        Permission.USER_SEARCH,
        Permission.USER_CREATE,
        Permission.USER_UPDATE,
        Permission.USER_ACTIVATE,
        Permission.USER_REACTIVATE,
    },
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
    },
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
        Permission.ROLE_MANAGE,
        Permission.POLICY_MANAGE,
        Permission.AUDIT_READ,
    },
}


def parse_role(role_str: str) -> Role:
    """Normalize string to Role enum (case-insensitive lookup)."""
    if not role_str:
        raise ValueError("Role cannot be empty")
    for r in Role:
        if r.value.lower() == role_str.strip().lower():
            return r
    raise ValueError(f"Unknown role: {role_str}")


def get_role_permissions(role: Role) -> Set[Permission]:
    """Return all permissions granted to a given role."""
    return ROLE_PERMISSIONS.get(role, set())


def get_role_level(role: Role) -> int:
    """Return numeric hierarchy level of a role."""
    return ROLE_HIERARCHY.get(role, 0)
