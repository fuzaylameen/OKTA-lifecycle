import asyncio
import csv
import io

from app.services.user_service import UserService


class BulkUserService:

    def __init__(self):
        self.user_service = UserService()

        # Maximum number of Okta operations running at once
        self.semaphore = asyncio.Semaphore(10)

    async def bulk_provision(self, user_ids: list[str]):

        async def process_user(user_id):

            async with self.semaphore:

                try:
                    result = await self.user_service.provision_user(
                        user_id
                    )

                    return {
                        "user_id": user_id,
                        "status": "success",
                        "action": "provision",
                        "result": result
                    }

                except Exception as e:

                    return {
                        "user_id": user_id,
                        "status": "failed",
                        "action": "provision",
                        "error": str(e)
                    }

        tasks = [
            process_user(user_id)
            for user_id in user_ids
        ]

        results = await asyncio.gather(*tasks)

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

        async def process_user(user_id):

            async with self.semaphore:

                try:
                    result = await self.user_service.deactivate_user(
                        user_id
                    )

                    return {
                        "user_id": user_id,
                        "status": "success",
                        "action": "deactivate",
                        "result": result
                    }

                except Exception as e:

                    return {
                        "user_id": user_id,
                        "status": "failed",
                        "action": "deactivate",
                        "error": str(e)
                    }

        tasks = [
            process_user(user_id)
            for user_id in user_ids
        ]

        results = await asyncio.gather(*tasks)

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

        async def process_user(user_id):

            async with self.semaphore:

                try:
                    result = await self.user_service.delete_user(
                        user_id
                    )

                    return {
                        "user_id": user_id,
                        "status": "success",
                        "action": "delete",
                        "result": result
                    }

                except Exception as e:

                    return {
                        "user_id": user_id,
                        "status": "failed",
                        "action": "delete",
                        "error": str(e)
                    }

        tasks = [
            process_user(user_id)
            for user_id in user_ids
        ]

        results = await asyncio.gather(*tasks)

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

        content = await file.read()

        text = content.decode("utf-8-sig")

        reader = csv.DictReader(
            io.StringIO(text)
        )

        rows = list(reader)

        async def process_row(row_number, row):

            async with self.semaphore:

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

                    return {
                        "row": row_number,
                        "email": email,
                        "status": "success",
                        "action": "create",
                        "user": result
                    }

                except Exception as e:

                    return {
                        "row": row_number,
                        "email": row.get("email"),
                        "status": "failed",
                        "action": "create",
                        "error": str(e)
                    }

        tasks = [
            process_row(row_number, row)
            for row_number, row in enumerate(
                rows,
                start=2
            )
        ]

        results = await asyncio.gather(*tasks)

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