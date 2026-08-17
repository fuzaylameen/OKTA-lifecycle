from app.services.okta_client import OktaClient


class GroupService:

    def __init__(self):

        self.okta = OktaClient()

    async def list_groups(self):

        return await self.okta.request(
            "GET",
            "/api/v1/groups"
        )

    async def add_user(
        self,
        group_id,
        user_id
    ):

        return await self.okta.request(
            "PUT",
            f"/api/v1/groups/{group_id}/users/{user_id}"
        )

    async def remove_user(
        self,
        group_id,
        user_id
    ):

        return await self.okta.request(
            "DELETE",
            f"/api/v1/groups/{group_id}/users/{user_id}"
        )

    async def move_user(
        self,
        user_id,
        old_group_id,
        new_group_id
    ):

        await self.remove_user(
            old_group_id,
            user_id
        )

        await self.add_user(
            new_group_id,
            user_id
        )

        return {
            "user_id": user_id,
            "old_group": old_group_id,
            "new_group": new_group_id
        }