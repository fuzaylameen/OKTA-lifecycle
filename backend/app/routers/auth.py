from fastapi import APIRouter, Depends, HTTPException, status
from app.auth.jwt_handler import create_user_token
from app.auth.dependencies import get_current_user
from app.schemas.auth import Token, TokenRequest
from app.authorization.models import AuthContext
from app.authorization.roles import (
    Role,
    get_role_permissions,
    resolve_role_from_okta_groups,
)
from app.services.user_service import UserService

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)

user_service = UserService()


@router.post("/token", response_model=Token)
async def generate_token(request: TokenRequest):
    """
    Authenticate an Okta user by email, derive their role from actual Okta group membership,
    and issue a cryptographically signed User JWT.
    """
    email = request.email.strip()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email cannot be empty"
        )

    # 1. Lookup user in Okta directory
    try:
        okta_user = await user_service.get_user_by_email(email)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: User '{email}' not found in Okta directory",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not okta_user or not okta_user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: User '{email}' not found in Okta directory",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = okta_user["id"]
    profile = okta_user.get("profile", {})
    actual_email = profile.get("email") or profile.get("login") or email

    # 2. Retrieve user's assigned Okta groups
    try:
        user_groups = await user_service.get_user_groups(user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve groups for user from Okta: {str(e)}"
        )

    group_names = []
    if isinstance(user_groups, list):
        for g in user_groups:
            p = g.get("profile", {})
            name = p.get("name") or g.get("name")
            if name:
                group_names.append(name)

    # 3. Map Okta group to backend application role
    try:
        role_enum = resolve_role_from_okta_groups(group_names)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Authorization failed: {str(e)}"
        )

    # 4. Issue User JWT
    permissions = [p.value for p in get_role_permissions(role_enum)]

    token = create_user_token(
        user_id=user_id,
        email=actual_email,
        role=role_enum.value,
        custom_claims={"permissions": permissions, "okta_groups": group_names}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role_enum.value,
        "user_id": user_id,
        "email": actual_email,
        "permissions": permissions
    }


@router.get("/me")
async def get_current_user_profile(
    current_user: AuthContext = Depends(get_current_user)
):
    """
    Return currently authenticated user identity, role, and granted permissions.
    """
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role.value,
        "permissions": [p.value for p in current_user.permissions]
    }

