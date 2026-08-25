from fastapi import APIRouter, Depends, HTTPException, status
from app.auth.jwt_handler import create_user_token
from app.auth.dependencies import get_current_user
from app.schemas.auth import Token, TokenRequest
from app.authorization.models import AuthContext
from app.authorization.roles import parse_role, get_role_permissions

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


@router.post("/token", response_model=Token)
async def generate_token(request: TokenRequest):
    """
    Issue a cryptographically signed User JWT with assigned role and permissions.
    Used for user login, integration, and testing.
    """
    try:
        role_enum = parse_role(request.role)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    permissions = [p.value for p in get_role_permissions(role_enum)]

    token = create_user_token(
        user_id=request.user_id,
        email=request.email,
        role=role_enum.value,
        custom_claims={"permissions": permissions}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role_enum.value,
        "user_id": request.user_id,
        "email": request.email,
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
