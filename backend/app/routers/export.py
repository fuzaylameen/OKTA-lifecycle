import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.services.user_service import UserService
from app.authorization.permissions import Permission
from app.authorization.models import AuthContext
from app.authorization.dependencies import require_permission


router = APIRouter(
    prefix="/api/export",
    tags=["Export"]
)

service = UserService()


@router.get("/users.csv")
async def export_users(
    current_user: AuthContext = Depends(require_permission(Permission.USER_READ))
):
    users = await service.list_users()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "ID",
        "First Name",
        "Last Name",
        "Email",
        "Login",
        "Status"
    ])

    for user in users:
        profile = user.get("profile", {})

        writer.writerow([
            user.get("id"),
            profile.get("firstName"),
            profile.get("lastName"),
            profile.get("email"),
            profile.get("login"),
            user.get("status")
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=users.csv"
        }
    )