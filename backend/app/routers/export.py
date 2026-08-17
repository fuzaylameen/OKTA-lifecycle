import csv
import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.user_service import UserService


router = APIRouter(
    prefix="/api/export",
    tags=["Export"]
)

service = UserService()


@router.get("/users.csv")
async def export_users():

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