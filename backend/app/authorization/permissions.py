from enum import Enum


class Permission(str, Enum):
    # Viewer & above
    USER_READ = "user:read"
    USER_LIST = "user:list"
    USER_SEARCH = "user:search"
    AUDIT_READ = "audit:read"

    # Operator & above
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_ACTIVATE = "user:activate"
    USER_REACTIVATE = "user:reactivate"

    # Manager & above
    USER_SUSPEND = "user:suspend"
    USER_DEPROVISION = "user:deprovision"

    # Admin only
    ROLE_MANAGE = "role:manage"
    POLICY_MANAGE = "policy:manage"
