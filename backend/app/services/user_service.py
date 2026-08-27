import json
from datetime import datetime, timezone, timedelta

from app.services.okta_client import OktaClient
from app.core.config import settings

from app.db.database import SessionLocal
from app.db.models import AuditLog


class UserService:

    def __init__(self):
        self.okta = OktaClient()

    # ============================================================
    # AUDIT LOGGING
    # ============================================================

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

    # ============================================================
    # USER LIST / READ OPERATIONS
    # ============================================================

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

    async def list_user_groups(self, user_id):

        return await self.okta.request(
            "GET",
            f"/api/v1/users/{user_id}/groups"
        )

    async def get_user(self, user_id):

        return await self.okta.request(
            "GET",
            f"/api/v1/users/{user_id}"
        )

    # ============================================================
    # CREATE USER
    # ============================================================

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

    # ============================================================
    # PROVISION USER
    # ============================================================

    async def provision_user(self, user_id):

        """
        Handle a PROVISIONED user using Okta's reactivation
        lifecycle endpoint.
        """

        try:

            result = await self.okta.request(
                "POST",
                f"/api/v1/users/{user_id}/lifecycle/reactivate",
                params={
                    "sendEmail": "false"
                }
            )

            self._create_log(
                action="PROVISION_USER",
                user_id=user_id,
                new_value="ACTIVE",
                status="SUCCESS",
                message="User reactivated successfully"
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

    # ============================================================
    # ACTIVATE USER
    # ============================================================

    async def activate_user(self, user_id, send_email=False):

        """
        Activate a STAGED or DEPROVISIONED user.

        This uses:
            POST /lifecycle/activate

        This is different from:
            PROVISIONED -> /lifecycle/reactivate
        """

        try:

            result = await self.okta.request(
                "POST",
                f"/api/v1/users/{user_id}/lifecycle/activate",
                params={
                    "sendEmail": str(send_email).lower()
                }
            )

            self._create_log(
                action="ACTIVATE_USER",
                user_id=user_id,
                new_value="ACTIVE",
                status="SUCCESS",
                message="User activated successfully"
            )

            return result

        except Exception as e:

            self._create_log(
                action="ACTIVATE_USER",
                user_id=user_id,
                status="FAILED",
                message=str(e)
            )

            raise

    # ============================================================
    # DEACTIVATE USER
    # ============================================================

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

    # ============================================================
    # BULK DEACTIVATE
    # ============================================================

    async def bulk_deactivate(self, user_ids):

        """
        Sequentially deactivates each user through the existing
        deactivate_user() method.

        Each individual operation gets its own AuditLog row.
        """

        results = []

        for user_id in user_ids:

            try:

                result = await self.deactivate_user(user_id)

                results.append({
                    "user_id": user_id,
                    "status": "success",
                    "result": result
                })

            except Exception as e:

                results.append({
                    "user_id": user_id,
                    "status": "failed",
                    "error": str(e)
                })

        return {
            "total": len(user_ids),
            "successful": sum(
                1
                for r in results
                if r["status"] == "success"
            ),
            "failed": sum(
                1
                for r in results
                if r["status"] == "failed"
            ),
            "results": results
        }

    # ============================================================
    # UNSUSPEND USER
    # ============================================================

    async def unsuspend_user(self, user_id):

        """
        Reactivate a SUSPENDED user.

        SUSPENDED -> ACTIVE

        Uses:
            POST /lifecycle/unsuspend
        """

        try:

            result = await self.okta.request(
                "POST",
                f"/api/v1/users/{user_id}/lifecycle/unsuspend"
            )

            self._create_log(
                action="UNSUSPEND_USER",
                user_id=user_id,
                old_value="SUSPENDED",
                new_value="ACTIVE",
                status="SUCCESS",
                message="User unsuspended successfully"
            )

            return result

        except Exception as e:

            self._create_log(
                action="UNSUSPEND_USER",
                user_id=user_id,
                status="FAILED",
                message=str(e)
            )

            raise

    # ============================================================
    # UPDATE USER PROFILE
    # ============================================================

    async def update_profile(self, user_id, profile_changes):

        """
        Partially updates an Okta user's profile.

        Reads the current profile first so the audit log
        captures the old and new values for the changed fields.
        """

        try:

            before = await self.okta.request(
                "GET",
                f"/api/v1/users/{user_id}"
            )

            before_profile = (
                before.get("profile", {})
                if isinstance(before, dict)
                else {}
            )

            old_values = {
                field: before_profile.get(field)
                for field in profile_changes
            }

            result = await self.okta.request(
                "POST",
                f"/api/v1/users/{user_id}",
                json={
                    "profile": profile_changes
                }
            )

            self._create_log(
                action="UPDATE_PROFILE",
                user_id=user_id,
                old_value=json.dumps(old_values),
                new_value=json.dumps(profile_changes),
                status="SUCCESS",
                message="User profile updated successfully"
            )

            return result

        except Exception as e:

            self._create_log(
                action="UPDATE_PROFILE",
                user_id=user_id,
                status="FAILED",
                message=str(e)
            )

            raise

    # ============================================================
    # DELETE USER
    # ============================================================

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
    # SUSPEND USER
    # ============================================================

    async def suspend_user(self, user_id, reason=None):

        try:

            result = await self.okta.request(
                "POST",
                f"/api/v1/users/{user_id}/lifecycle/suspend"
            )

            self._create_log(
                action="SUSPEND_USER",
                user_id=user_id,
                old_value="ACTIVE",
                new_value="SUSPENDED",
                status="SUCCESS",
                message=(
                    f"User suspended. Reason: {reason}"
                    if reason
                    else "User suspended"
                )
            )

            return result

        except Exception as e:

            self._create_log(
                action="SUSPEND_USER",
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

        # --------------------------------------------------------
        # No passwordChanged information
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Parse passwordChanged
        # --------------------------------------------------------

        try:

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

        # --------------------------------------------------------
        # Make datetime timezone-aware
        # --------------------------------------------------------

        if password_changed_dt.tzinfo is None:

            password_changed_dt = password_changed_dt.replace(
                tzinfo=timezone.utc
            )

        # --------------------------------------------------------
        # Calculate expiry
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Determine status
        # --------------------------------------------------------

        if remaining_seconds <= 0:

            status = "EXPIRED"

        elif days_remaining <= settings.PASSWORD_EXPIRY_WARNING_DAYS:

            status = "EXPIRING_SOON"

        else:

            status = "ACTIVE"

        # --------------------------------------------------------
        # Return result
        # --------------------------------------------------------

        return {
            "user_id": user_id,
            "email": email,
            "password_changed": password_changed_dt.isoformat(),
            "expiry_date": expiry_date.isoformat(),
            "days_remaining": max(days_remaining, 0),
            "status": status,
            "expiry_days": settings.PASSWORD_EXPIRY_DAYS
        }

    # ============================================================
    # GET PASSWORD EXPIRY
    # ============================================================

    async def get_password_expiry(self, user_id):

        """
        Get password expiry information for a single user.
        """

        user = await self.okta.request(
            "GET",
            f"/api/v1/users/{user_id}"
        )

        return self._calculate_password_expiry(user)

    # ============================================================
    # LIST PASSWORD EXPIRY
    # ============================================================

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

    # ============================================================
    # FORCE PASSWORD EXPIRY
    # ============================================================

    async def expire_password(self, user_id):

        """
        Force a user's password to expire in Okta.

        The user will be required to change their password
        during the next login.
        """

        try:

            # ----------------------------------------------------
            # Retrieve user for audit email
            # ----------------------------------------------------

            user = await self.okta.request(
                "GET",
                f"/api/v1/users/{user_id}"
            )

            profile = user.get("profile", {})

            user_email = (
                profile.get("email")
                or profile.get("login")
            )

            # ----------------------------------------------------
            # Expire password
            # ----------------------------------------------------

            result = await self.okta.request(
                "POST",
                f"/api/v1/users/{user_id}/lifecycle/expire_password"
            )

            # ----------------------------------------------------
            # Audit success
            # ----------------------------------------------------

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

            # ----------------------------------------------------
            # Audit failure
            # ----------------------------------------------------

            self._create_log(
                action="EXPIRE_PASSWORD",
                user_id=user_id,
                status="FAILED",
                message=str(e)
            )

            raise