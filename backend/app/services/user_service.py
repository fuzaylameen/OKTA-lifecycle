from app.services.okta_client import OktaClient

from app.db.database import SessionLocal
from app.db.models import AuditLog


class UserService:

    def __init__(self):
        self.okta = OktaClient()

    def _create_log(
        self,
        action,
        user_id=None,
        user_email=None,
        old_value=None,
        new_value=None,
        status="SUCCESS",
        message=None
    ):
        """
        Create an audit log entry.
        """

        db = SessionLocal()

        try:

            log = AuditLog(
                action=action,
                user_id=str(user_id) if user_id else None,
                user_email=user_email,
                old_value=old_value,
                new_value=new_value,
                status=status,
                message=message
            )

            db.add(log)
            db.commit()

        finally:

            db.close()

    async def list_users(self):

        return await self.okta.request(
            "GET",
            "/api/v1/users"
        )

    async def list_deprovisioned_users(self):

        return await self.okta.request(
            "GET",
            "/api/v1/users",
            params={
                "filter": 'status eq "DEPROVISIONED"'
            }
        )

    async def list_all_users(self):

        users = await self.list_users()
        deprovisioned_users = await self.list_deprovisioned_users()
        return users + deprovisioned_users


    async def create_user(self, user_data):

        try:

            result = await self.okta.request(
                "POST",
                "/api/v1/users",
                params={
                    "activate": "false"
                },
                json={
                    "profile": {
                        "firstName": user_data["first_name"],
                        "lastName": user_data["last_name"],
                        "email": user_data["email"],
                        "login": user_data["email"]
                    }
                }
            )

            # Log successful creation
            self._create_log(
                action="CREATE_USER",
                user_id=result.get("id"),
                user_email=user_data["email"],
                new_value="CREATED",
                status="SUCCESS",
                message="User created successfully in Okta"
            )

            return result

        except Exception as e:

            self._create_log(
                action="CREATE_USER",
                user_email=user_data.get("email"),
                status="FAILED",
                message=str(e)
            )

            raise

    async def provision_user(self, user_id):

        try:

            result = await self.okta.request(
                "POST",
                f"/api/v1/users/{user_id}/lifecycle/activate",
                params={
                    "sendEmail": "true"
                }
            )

            self._create_log(
                action="PROVISION_USER",
                user_id=user_id,
                new_value="ACTIVE",
                status="SUCCESS",
                message="User provisioned successfully"
            )

            return result

        except Exception as e:

            self._create_log(
                action="PROVISION_USER",
                user_id=user_id,
                status="FAILED",
                message=str(e)
            )

            raise


    async def deactivate_user(self, user_id):

        try:

            result = await self.okta.request(
                "POST",
                f"/api/v1/users/{user_id}/lifecycle/deactivate",
                params={
                    "sendEmail": "false"
                }
            )

            self._create_log(
                action="DEACTIVATE_USER",
                user_id=user_id,
                old_value="ACTIVE",
                new_value="DEACTIVATED",
                status="SUCCESS",
                message="User deactivated successfully"
            )

            return result

        except Exception as e:

            self._create_log(
                action="DEACTIVATE_USER",
                user_id=user_id,
                status="FAILED",
                message=str(e)
            )

            raise

    async def delete_user(self, user_id):

        try:

            result = await self.okta.request(
                "DELETE",
                f"/api/v1/users/{user_id}"
            )

            self._create_log(
                action="DELETE_USER",
                user_id=user_id,
                old_value="DEACTIVATED",
                new_value="DELETED",
                status="SUCCESS",
                message="User permanently deleted"
            )

            return result

        except Exception as e:

            self._create_log(
                action="DELETE_USER",
                user_id=user_id,
                status="FAILED",
                message=str(e)
            )

            raise