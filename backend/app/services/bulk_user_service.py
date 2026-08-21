from app.services.user_service import UserService


class BulkUserService:

    def __init__(self):
        self.user_service = UserService()

    async def bulk_provision(self, user_ids: list[str]):

        results = []

        for user_id in user_ids:

            try:
                result = await self.user_service.provision_user(user_id)

                results.append({
                    "user_id": user_id,
                    "status": "success",
                    "action": "provision",
                    "result": result
                })

            except Exception as e:

                results.append({
                    "user_id": user_id,
                    "status": "failed",
                    "action": "provision",
                    "error": str(e)
                })

        return {
            "total": len(user_ids),
            "successful": sum(
                1 for r in results if r["status"] == "success"
            ),
            "failed": sum(
                1 for r in results if r["status"] == "failed"
            ),
            "results": results
        }

    async def bulk_deactivate(self, user_ids: list[str]):

        results = []

        for user_id in user_ids:

            try:
                result = await self.user_service.deactivate_user(user_id)

                results.append({
                    "user_id": user_id,
                    "status": "success",
                    "action": "deactivate",
                    "result": result
                })

            except Exception as e:

                results.append({
                    "user_id": user_id,
                    "status": "failed",
                    "action": "deactivate",
                    "error": str(e)
                })

        return {
            "total": len(user_ids),
            "successful": sum(
                1 for r in results if r["status"] == "success"
            ),
            "failed": sum(
                1 for r in results if r["status"] == "failed"
            ),
            "results": results
        }

    async def bulk_delete(self, user_ids: list[str]):

        results = []

        for user_id in user_ids:

            try:
                result = await self.user_service.delete_user(user_id)

                results.append({
                    "user_id": user_id,
                    "status": "success",
                    "action": "delete",
                    "result": result
                })

            except Exception as e:

                results.append({
                    "user_id": user_id,
                    "status": "failed",
                    "action": "delete",
                    "error": str(e)
                })

        return {
            "total": len(user_ids),
            "successful": sum(
                1 for r in results if r["status"] == "success"
            ),
            "failed": sum(
                1 for r in results if r["status"] == "failed"
            ),
            "results": results
        }

    async def import_users_from_csv(self, file):

        import csv
        import io

        content = await file.read()

        text = content.decode("utf-8-sig")

        reader = csv.DictReader(
            io.StringIO(text)
        )

        results = []

        for row_number, row in enumerate(
            reader,
            start=2
        ):

            try:

                first_name = (
                    row.get("first_name") or ""
                ).strip()

                last_name = (
                    row.get("last_name") or ""
                ).strip()

                email = (
                    row.get("email") or ""
                ).strip()

                # Validate required fields
                if not first_name:
                    raise ValueError(
                        "first_name is required"
                    )

                if not last_name:
                    raise ValueError(
                        "last_name is required"
                    )

                if not email:
                    raise ValueError(
                        "email is required"
                    )

                # Create user using the existing
                # UserService
                result = await self.user_service.create_user(
                    {
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email
                    }
                )

                results.append({
                    "row": row_number,
                    "email": email,
                    "status": "success",
                    "action": "create",
                    "user": result
                })

            except Exception as e:

                results.append({
                    "row": row_number,
                    "email": row.get("email"),
                    "status": "failed",
                    "action": "create",
                    "error": str(e)
                })

        return {
            "total": len(results),
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