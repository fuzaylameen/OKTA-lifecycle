from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from app.auth.jwt_handler import verify_user_token, AuthenticationError
from app.authorization.models import AuthContext
from app.authorization.roles import parse_role

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> AuthContext:
    """
    FastAPI dependency that extracts the Bearer token from the Authorization header,
    verifies it, and returns the validated AuthContext.
    """
    if not credentials or not credentials.credentials:
        raise AuthenticationError("Authorization header is missing or malformed")

    payload = verify_user_token(credentials.credentials)

    user_id = payload.get("sub")
    email = payload.get("email")
    role_str = payload.get("role")

    role = parse_role(role_str)

    return AuthContext(
        user_id=user_id,
        email=email,
        role=role,
        claims=payload
    )
