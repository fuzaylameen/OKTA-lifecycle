import time
import uuid
import httpx
import jwt

from app.core.config import settings


class OktaClient:

    def __init__(self):

        self.domain = settings.OKTA_DOMAIN.rstrip("/")
        print(f"Okta domain: {self.domain}")

        self.client_id = settings.OKTA_CLIENT_ID

        with open(
            settings.OKTA_PRIVATE_KEY_PATH,
            "r"
        ) as f:
            self.private_key = f.read()

        self.access_token = None
        self.token_expiry = 0

    def _create_client_assertion(self):

        now = int(time.time())

        payload = {
            "iss": self.client_id,
            "sub": self.client_id,
            "aud": f"{self.domain}/oauth2/v1/token",
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid.uuid4())
        }

        return jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256"
        )

    async def get_access_token(self):

        if (
            self.access_token
            and time.time() < self.token_expiry - 60
        ):
            return self.access_token

        assertion = self._create_client_assertion()

        data = {
            "grant_type": "client_credentials",
            "scope": (
                "okta.users.manage "
                "okta.groups.manage "
                "okta.logs.read"
            ),
            "client_assertion_type":
                "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion
        }


        # https://integrator-8486226.okta.com/oauth2/v1/token
        async with httpx.AsyncClient() as client:

            response = await client.post(
                f"{self.domain}/oauth2/v1/token",
                data=data,
                headers={
                    "Accept": "application/json",
                    "Content-Type":
                        "application/x-www-form-urlencoded"
                }
            )

        response.raise_for_status()

        token_data = response.json()

        self.access_token = token_data["access_token"]

        self.token_expiry = (
            time.time()
            + token_data.get("expires_in", 3600)
        )

        return self.access_token

    async def request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ):

        token = await self.get_access_token()

        headers = kwargs.pop("headers", {})

        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/json"

        async with httpx.AsyncClient() as client:

            response = await client.request(
                method,
                f"{self.domain}{endpoint}",
                headers=headers,
                **kwargs
            )

        response.raise_for_status()

        if response.status_code == 204:
            return None

        return response.json()