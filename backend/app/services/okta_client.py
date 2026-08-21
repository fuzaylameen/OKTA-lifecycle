import time
import uuid
import base64
import hashlib

import httpx
import jwt

from cryptography.hazmat.primitives import serialization

from app.core.config import settings


class OktaClient:

    def __init__(self):

        self.domain = settings.OKTA_DOMAIN.rstrip("/")
        print(f"Okta domain: {self.domain}")

        self.client_id = settings.OKTA_CLIENT_ID

        # Load the private key used for client authentication
        with open(
            settings.OKTA_PRIVATE_KEY_PATH,
            "rb"
        ) as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(),
                password=None
            )

        self.access_token = None
        self.token_expiry = 0

    # =========================================================
    # CLIENT ASSERTION
    # =========================================================

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

    # =========================================================
    # DPOP PUBLIC JWK
    # =========================================================

    def _get_dpop_jwk(self):

        public_key = self.private_key.public_key()

        numbers = public_key.public_numbers()

        n = base64.urlsafe_b64encode(
            numbers.n.to_bytes(
                (numbers.n.bit_length() + 7) // 8,
                byteorder="big"
            )
        ).rstrip(b"=").decode("ascii")

        e = base64.urlsafe_b64encode(
            numbers.e.to_bytes(
                (numbers.e.bit_length() + 7) // 8,
                byteorder="big"
            )
        ).rstrip(b"=").decode("ascii")

        return {
            "kty": "RSA",
            "n": n,
            "e": e,
            "alg": "RS256"
        }

    # =========================================================
    # DPOP PROOF
    # =========================================================

    def _create_dpop_proof(
        self,
        method,
        url,
        access_token=None,
        nonce=None
    ):

        now = int(time.time())

        header = {
            "typ": "dpop+jwt",
            "alg": "RS256",
            "jwk": self._get_dpop_jwk()
        }

        payload = {
            "jti": str(uuid.uuid4()),
            "htm": method.upper(),
            "htu": url,
            "iat": now
        }

        # Add access-token hash when using the token
        # against the Okta API.
        if access_token:

            token_hash = hashlib.sha256(
                access_token.encode("ascii")
            ).digest()

            payload["ath"] = (
                base64.urlsafe_b64encode(
                    token_hash
                )
                .rstrip(b"=")
                .decode("ascii")
            )

        # Add nonce when Okta requires one.
        if nonce:

            payload["nonce"] = nonce

        return jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256",
            headers=header
        )

    # =========================================================
    # GET ACCESS TOKEN
    # =========================================================

    async def get_access_token(self):

        # Reuse the existing access token if it is still valid.
        if (
            self.access_token
            and time.time() < self.token_expiry - 60
        ):
            return self.access_token

        token_url = (
            f"{self.domain}/oauth2/v1/token"
        )

        # -----------------------------------------------------
        # FIRST CLIENT ASSERTION
        # -----------------------------------------------------

        assertion = (
            self._create_client_assertion()
        )

        # -----------------------------------------------------
        # FIRST DPOP PROOF
        # -----------------------------------------------------

        dpop_proof = (
            self._create_dpop_proof(
                method="POST",
                url=token_url
            )
        )

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

        print("================================")
        print("OKTA TOKEN REQUEST")
        print("================================")
        print("Token URL:", token_url)
        print("Client ID:", self.client_id)
        print("Grant Type: client_credentials")
        print("DPoP: enabled")
        print("================================")

        async with httpx.AsyncClient() as client:

            # -------------------------------------------------
            # FIRST TOKEN REQUEST
            # -------------------------------------------------

            response = await client.post(
                token_url,
                data=data,
                headers={
                    "Accept": "application/json",
                    "Content-Type":
                        "application/x-www-form-urlencoded",
                    "DPoP": dpop_proof
                }
            )

            # -------------------------------------------------
            # DPOP NONCE RETRY
            # -------------------------------------------------

            if response.status_code == 400:

                try:
                    error_data = response.json()
                except Exception:
                    error_data = {}

                if (
                    error_data.get("error")
                    == "use_dpop_nonce"
                ):

                    nonce = (
                        response.headers.get(
                            "dpop-nonce"
                        )
                    )

                    print(
                        "DPoP nonce required:",
                        nonce
                    )

                    # IMPORTANT:
                    #
                    # Generate a NEW client assertion.
                    #
                    # The previous assertion has already been
                    # processed by Okta and cannot be reused.
                    #
                    assertion = (
                        self._create_client_assertion()
                    )

                    data["client_assertion"] = (
                        assertion
                    )

                    # Generate a NEW DPoP proof containing
                    # the nonce returned by Okta.
                    dpop_proof = (
                        self._create_dpop_proof(
                            method="POST",
                            url=token_url,
                            nonce=nonce
                        )
                    )

                    # -------------------------------------------------
                    # SECOND TOKEN REQUEST
                    # -------------------------------------------------

                    response = await client.post(
                        token_url,
                        data=data,
                        headers={
                            "Accept":
                                "application/json",

                            "Content-Type":
                                "application/x-www-form-urlencoded",

                            "DPoP":
                                dpop_proof
                        }
                    )

        # -----------------------------------------------------
        # TOKEN RESPONSE DEBUG
        # -----------------------------------------------------

        print("================================")
        print("OKTA TOKEN RESPONSE")
        print("================================")
        print(
            "Status:",
            response.status_code
        )
        print(
            "Response:",
            response.text
        )
        print("================================")

        # Raise HTTP error if token request failed.
        response.raise_for_status()

        token_data = response.json()

        # Save access token.
        self.access_token = (
            token_data["access_token"]
        )

        # Save expiry time.
        self.token_expiry = (
            time.time()
            + token_data.get(
                "expires_in",
                3600
            )
        )

        return self.access_token

    # =========================================================
    # OKTA API REQUEST
    # =========================================================

    async def request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ):

        # Get access token.
        token = (
            await self.get_access_token()
        )

        url = (
            f"{self.domain}{endpoint}"
        )

        # Create DPoP proof for the API request.
        dpop_proof = (
            self._create_dpop_proof(
                method=method,
                url=url,
                access_token=token
            )
        )

        headers = kwargs.pop(
            "headers",
            {}
        )

        # DPoP-bound access token must use DPoP
        # authentication.
        headers["Authorization"] = (
            f"DPoP {token}"
        )

        headers["DPoP"] = (
            dpop_proof
        )

        headers["Accept"] = (
            "application/json"
        )

        async with httpx.AsyncClient() as client:

            response = await client.request(
                method,
                url,
                headers=headers,
                **kwargs
            )

        # Print API errors.
        if response.status_code >= 400:

            print("================================")
            print("OKTA API ERROR")
            print("================================")
            print("Method:", method)
            print("URL:", url)
            print(
                "Status:",
                response.status_code
            )
            print(
                "Response:",
                response.text
            )
            print("================================")

        response.raise_for_status()

        # No content.
        if response.status_code == 204:
            return None

        # Empty response.
        if not response.text:
            return None

        return response.json()