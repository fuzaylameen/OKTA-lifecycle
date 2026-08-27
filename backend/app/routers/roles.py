from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db

from app.db.models import (
    Permission,
    Role,
    RolePermission,
)

from app.dependencies.authorization import (
    Actor,
    require_permission,
)

from app.schemas.authorization import (
    ActorRoleAssign,
    PermissionCreate,
    RoleCreate,
    RolePermissionUpdate,
)

from app.services.rbac_service import (
    RBACService,
)


router = APIRouter(
    prefix="/roles",
    tags=["Authorization - Roles"]
)


@router.get("/")
def list_roles(
    actor: Actor = Depends(
        require_permission("user:read")
    ),
    db: Session = Depends(get_db),
):

    roles = db.scalars(
        select(Role)
        .order_by(Role.name)
    ).all()


    result = []


    for role in roles:

        permissions = db.scalars(

            select(Permission)

            .join(
                RolePermission,
                RolePermission.permission_id
                ==
                Permission.id
            )

            .where(
                RolePermission.role_id ==
                role.id
            )

        ).all()


        result.append({

            "id": role.id,

            "name": role.name,

            "description":
            role.description,

            "active":
            role.active,

            "permissions": [
                p.name
                for p in permissions
            ]
        })


    return result


@router.post("/")
def create_role(
    request: RoleCreate,

    actor: Actor = Depends(
        require_permission("role:create")
    ),

    db: Session = Depends(get_db),
):

    name = request.name.strip().upper()


    if db.scalar(
        select(Role)
        .where(Role.name == name)
    ):

        raise HTTPException(
            status_code=409,
            detail="Role already exists"
        )


    role = Role(
        name=name,
        description=request.description
    )


    db.add(role)

    db.commit()

    db.refresh(role)


    return {
        "success": True,
        "role": role.name,
        "id": role.id
    }


@router.post("/permissions")
def create_permission(
    request: PermissionCreate,

    actor: Actor = Depends(
        require_permission("role:create")
    ),

    db: Session = Depends(get_db),
):

    name = request.name.strip()


    if db.scalar(
        select(Permission)
        .where(Permission.name == name)
    ):

        raise HTTPException(
            status_code=409,
            detail="Permission already exists"
        )


    permission = Permission(
        name=name,
        description=request.description
    )


    db.add(permission)

    db.commit()

    db.refresh(permission)


    return {
        "success": True,
        "permission": permission.name,
        "id": permission.id
    }


@router.put(
    "/{role_name}/permissions"
)
def update_role_permissions(

    role_name: str,

    request: RolePermissionUpdate,

    actor: Actor = Depends(
        require_permission("role:update")
    ),

    db: Session = Depends(get_db),
):

    try:

        role = (
            RBACService(db)
            .replace_role_permissions(
                role_name,
                request.permission_names
            )
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc)
        )


    return {
        "success": True,
        "role": role.name,
        "permissions":
            request.permission_names
    }


@router.post("/assign")
def assign_role(

    request: ActorRoleAssign,

    actor: Actor = Depends(
        require_permission("role:update")
    ),

    db: Session = Depends(get_db),
):

    try:

        RBACService(db).assign_role(
            request.actor_email,
            request.role_name
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=409,
            detail=str(exc)
        )


    return {
        "success": True,
        "actor_email":
            request.actor_email.lower(),
        "role":
            request.role_name.upper()
    }