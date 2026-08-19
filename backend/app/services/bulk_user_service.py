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