from datetime import datetime, timezone, timedelta

from app.services.okta_client import OktaClient
from app.core.config import settings

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

    # ============================================================
    # PASSWORD EXPIRY
    # ============================================================

    def _calculate_password_expiry(self, user):

        """
        Calculate password expiry information for an Okta user.
        """

        password_changed = user.get("passwordChanged")

        user_id = user.get("id")

        profile = user.get("profile", {})

        email = (
            profile.get("email")
            or profile.get("login")
        )

        # No passwordChanged information available
        if not password_changed:

            return {
                "user_id": user_id,
                "email": email,
                "password_changed": None,
                "expiry_date": None,
                "days_remaining": None,
                "status": "NO_PASSWORD_DATE",
                "expiry_days": settings.PASSWORD_EXPIRY_DAYS
            }

        try:

            # Convert Okta timestamp to datetime
            password_changed_dt = datetime.fromisoformat(
                password_changed.replace("Z", "+00:00")
            )

        except ValueError:

            return {
                "user_id": user_id,
                "email": email,
                "password_changed": password_changed,
                "expiry_date": None,
                "days_remaining": None,
                "status": "INVALID_PASSWORD_DATE",
                "expiry_days": settings.PASSWORD_EXPIRY_DAYS
            }

        # Make sure datetime is timezone-aware
        if password_changed_dt.tzinfo is None:

            password_changed_dt = password_changed_dt.replace(
                tzinfo=timezone.utc
            )

        expiry_date = (
    password_changed_dt
    + timedelta(
        days=settings.PASSWORD_EXPIRY_DAYS
    )
)

        now = datetime.now(timezone.utc)

        remaining_seconds = (
            expiry_date - now
        ).total_seconds()

        days_remaining = int(
            remaining_seconds // 86400
        )

        # Password already expired
        if remaining_seconds <= 0:

            status = "EXPIRED"

        # Password will expire within warning period
        elif days_remaining <= settings.PASSWORD_EXPIRY_WARNING_DAYS:

            status = "EXPIRING_SOON"

        else:

            status = "ACTIVE"

        return {
            "user_id": user_id,
            "email": email,
            "password_changed": password_changed_dt.isoformat(),
            "expiry_date": expiry_date.isoformat(),
            "days_remaining": max(days_remaining, 0),
            "status": status,
            "expiry_days": settings.PASSWORD_EXPIRY_DAYS
        }

    async def get_password_expiry(self, user_id):

        """
        Get password expiry information for a single user.
        """

        user = await self.okta.request(
            "GET",
            f"/api/v1/users/{user_id}"
        )

        return self._calculate_password_expiry(user)

    async def list_password_expiry(self):

        """
        Get password expiry information for all users.
        """

        users = await self.list_users()

        results = []

        for user in users:

            results.append(
                self._calculate_password_expiry(user)
            )

        return {
            "expiry_days": settings.PASSWORD_EXPIRY_DAYS,
            "warning_days": settings.PASSWORD_EXPIRY_WARNING_DAYS,
            "users": results
        }

    async def expire_password(self, user_id):

        """
        Force a user's password to expire in Okta.

        The user will be required to change their password
        during the next login.
        """

        try:

            # First retrieve the user so we can capture
            # the email for the audit log.
            user = await self.okta.request(
                "GET",
                f"/api/v1/users/{user_id}"
            )

            profile = user.get("profile", {})

            user_email = (
                profile.get("email")
                or profile.get("login")
            )

            # Expire password using Okta lifecycle API.
            result = await self.okta.request(
                "POST",
                f"/api/v1/users/{user_id}/lifecycle/expire_password"
            )

            self._create_log(
                action="EXPIRE_PASSWORD",
                user_id=user_id,
                user_email=user_email,
                old_value="PASSWORD_ACTIVE",
                new_value="PASSWORD_EXPIRED",
                status="SUCCESS",
                message="User password expired successfully"
            )

            return result

        except Exception as e:

            self._create_log(
                action="EXPIRE_PASSWORD",
                user_id=user_id,
                status="FAILED",
                message=str(e)
            )

            raise