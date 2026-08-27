import time
import uuid
from typing import Dict, Any, Optional
import jwt
from fastapi import HTTPException, status

from app.core.config import settings

VALID_ROLES = {"Auditor", "Manager", "Admin", "RoleManager", "Viewer", "Operator"}



def validate_role_str(role_str: str) -> str:
    """Validate and normalize role string against allowed system roles."""
    if not role_str:
        raise ValueError("Role cannot be empty")
    cleaned = str(role_str).strip().lower()
    if cleaned in ("viewer", "auditor"):
        return "Auditor"
    if cleaned in ("operator", "manager"):
        return "Manager"
    if cleaned == "admin":
        return "Admin"
    if cleaned in ("rolemanager", "role_manager", "role-manager", "role manager"):
        return "RoleManager"

    for valid_role in VALID_ROLES:
        if valid_role.lower() == cleaned:
            return valid_role
    raise ValueError(f"Unknown role: {role_str}")



class AuthenticationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


def create_user_token(
    user_id: str,
    email: str,
    role: str,
    expires_in_minutes: Optional[int] = None,
    custom_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a cryptographically signed User JWT with required identity and role claims.
    """
    # Verify role is valid
    normalized_role = validate_role_str(role)

    now = int(time.time())
    exp_minutes = expires_in_minutes or settings.USER_JWT_EXPIRE_MINUTES
    exp = now + (exp_minutes * 60)

    payload = {
        "iss": settings.USER_JWT_ISSUER,
        "aud": settings.USER_JWT_AUDIENCE,
        "sub": str(user_id),
        "email": email,
        "role": normalized_role,
        "iat": now,
        "exp": exp,
        "jti": str(uuid.uuid4()),
    }

    if custom_claims:
        payload.update(custom_claims)

    token = jwt.encode(
        payload,
        settings.USER_JWT_SECRET,
        algorithm=settings.USER_JWT_ALGORITHM
    )

    return token


def verify_user_token(token: str) -> Dict[str, Any]:
    """
    Strictly verify the user JWT signature and validate critical claims:
    - Signature validity
    - Expiration (exp)
    - Issuer (iss)
    - Audience (aud)
    - Required claims (sub, role)
    """
    if not token:
        raise AuthenticationError("Missing authentication token")

    try:
        payload = jwt.decode(
            token,
            settings.USER_JWT_SECRET,
            algorithms=[settings.USER_JWT_ALGORITHM],
            issuer=settings.USER_JWT_ISSUER,
            audience=settings.USER_JWT_AUDIENCE,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
                "require": ["exp", "iss", "aud", "sub", "role"]
            }
        )
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidIssuerError:
        raise AuthenticationError("Invalid token issuer")
    except jwt.InvalidAudienceError:
        raise AuthenticationError("Invalid token audience")
    except jwt.InvalidSignatureError:
        raise AuthenticationError("Invalid token signature")
    except jwt.MissingRequiredClaimError as e:
        raise AuthenticationError(f"Missing required claim: {str(e)}")
    except jwt.PyJWTError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")
    except Exception as e:
        raise AuthenticationError(f"Authentication failed: {str(e)}")

    # Verify role value in claim is a recognized system role
    try:
        validate_role_str(payload.get("role"))
    except ValueError:
        raise AuthenticationError(f"Token contains unrecognized role: {payload.get('role')}")

    return payload
