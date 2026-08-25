import time
import uuid
import httpx
import jwt

from app.core.config import settings


class OktaClient:

    def __init__(self):
        self.domain = settings.OKTA_DOMAIN.rstrip("/")
        self.client_id = settings.OKTA_CLIENT_ID

        print(f"Okta domain: {self.domain}")
        print(f"Okta client ID: {self.client_id}")

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

        assertion = jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256"
        )

        return assertion

    async def get_access_token(self):

        # Reuse existing token if it is still valid
        if (
            self.access_token
            and time.time() < self.token_expiry - 60
        ):
            return self.access_token

        # Create JWT client assertion
        assertion = self._create_client_assertion()

        # OAuth token request data
        data = {
            "grant_type": "client_credentials",

            "scope": "okta.users.read okta.users.manage",

            "client_assertion_type":
                "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",

            "client_assertion": assertion
        }

        token_url = f"{self.domain}/oauth2/v1/token"

        print("\n========== OKTA TOKEN REQUEST ==========")
        print("Token URL:", token_url)
        print("Grant type:", data["grant_type"])
        print("Client ID:", self.client_id)
        print("Scope:", data["scope"])
        print("========================================")

        async with httpx.AsyncClient() as client:

            response = await client.post(
                token_url,
                data=data,
                headers={
                    "Accept": "application/json",
                    "Content-Type":
                        "application/x-www-form-urlencoded"
                }
            )

        # Print the actual Okta error
        if response.status_code != 200:

            print("\n========== OKTA TOKEN ERROR ==========")
            print("Status:", response.status_code)
            print("Response:", response.text)
            print("======================================\n")

        response.raise_for_status()

        token_data = response.json()

        self.access_token = token_data["access_token"]

        self.token_expiry = (
            time.time()
            + token_data.get("expires_in", 3600)
        )

        print("Okta access token received successfully.")

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