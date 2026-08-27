import time
import pytest
import jwt
from fastapi import HTTPException

from app.core.config import settings
from app.auth.jwt_handler import create_user_token, verify_user_token, AuthenticationError
from app.authorization.roles import Role


def test_create_and_verify_valid_token():
    token = create_user_token(
        user_id="usr_123",
        email="alice@company.com",
        role="Admin"
    )
    assert token is not None
    assert isinstance(token, str)

    payload = verify_user_token(token)
    assert payload["sub"] == "usr_123"
    assert payload["email"] == "alice@company.com"
    assert payload["role"] == "Admin"
    assert payload["iss"] == settings.USER_JWT_ISSUER
    assert payload["aud"] == settings.USER_JWT_AUDIENCE


def test_expired_token_raises_401():
    # Issue a token that expired 10 seconds ago
    now = int(time.time())
    payload = {
        "iss": settings.USER_JWT_ISSUER,
        "aud": settings.USER_JWT_AUDIENCE,
        "sub": "usr_expired",
        "email": "expired@company.com",
        "role": "Viewer",
        "iat": now - 3600,
        "exp": now - 10,
    }
    expired_token = jwt.encode(payload, settings.USER_JWT_SECRET, algorithm=settings.USER_JWT_ALGORITHM)

    with pytest.raises(AuthenticationError) as exc_info:
        verify_user_token(expired_token)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_invalid_signature_raises_401():
    token = create_user_token(
        user_id="usr_tampered",
        email="tampered@company.com",
        role="Manager"
    )
    # Re-sign or tamper token
    tampered_token = token + "corrupted"

    with pytest.raises(AuthenticationError) as exc_info:
        verify_user_token(tampered_token)
    assert exc_info.value.status_code == 401


def test_wrong_secret_raises_401():
    now = int(time.time())
    payload = {
        "iss": settings.USER_JWT_ISSUER,
        "aud": settings.USER_JWT_AUDIENCE,
        "sub": "usr_wrong_secret",
        "email": "wrong@company.com",
        "role": "Admin",
        "iat": now,
        "exp": now + 3600,
    }
    forged_token = jwt.encode(payload, "wrong-secret-key-12345", algorithm=settings.USER_JWT_ALGORITHM)

    with pytest.raises(AuthenticationError) as exc_info:
        verify_user_token(forged_token)
    assert exc_info.value.status_code == 401


def test_invalid_issuer_raises_401():
    now = int(time.time())
    payload = {
        "iss": "untrusted-issuer",
        "aud": settings.USER_JWT_AUDIENCE,
        "sub": "usr_bad_iss",
        "email": "badiss@company.com",
        "role": "Admin",
        "iat": now,
        "exp": now + 3600,
    }
    bad_iss_token = jwt.encode(payload, settings.USER_JWT_SECRET, algorithm=settings.USER_JWT_ALGORITHM)

    with pytest.raises(AuthenticationError) as exc_info:
        verify_user_token(bad_iss_token)
    assert exc_info.value.status_code == 401
    assert "issuer" in exc_info.value.detail.lower()


def test_invalid_audience_raises_401():
    now = int(time.time())
    payload = {
        "iss": settings.USER_JWT_ISSUER,
        "aud": "wrong-audience",
        "sub": "usr_bad_aud",
        "email": "badaud@company.com",
        "role": "Admin",
        "iat": now,
        "exp": now + 3600,
    }
    bad_aud_token = jwt.encode(payload, settings.USER_JWT_SECRET, algorithm=settings.USER_JWT_ALGORITHM)

    with pytest.raises(AuthenticationError) as exc_info:
        verify_user_token(bad_aud_token)
    assert exc_info.value.status_code == 401
    assert "audience" in exc_info.value.detail.lower()


def test_missing_required_claims_raises_401():
    now = int(time.time())
    # Missing 'role' claim
    payload = {
        "iss": settings.USER_JWT_ISSUER,
        "aud": settings.USER_JWT_AUDIENCE,
        "sub": "usr_no_role",
        "email": "norole@company.com",
        "iat": now,
        "exp": now + 3600,
    }
    incomplete_token = jwt.encode(payload, settings.USER_JWT_SECRET, algorithm=settings.USER_JWT_ALGORITHM)

    with pytest.raises(AuthenticationError) as exc_info:
        verify_user_token(incomplete_token)
    assert exc_info.value.status_code == 401


def test_invalid_role_value_raises_401():
    now = int(time.time())
    payload = {
        "iss": settings.USER_JWT_ISSUER,
        "aud": settings.USER_JWT_AUDIENCE,
        "sub": "usr_fake_role",
        "email": "fakerole@company.com",
        "role": "SuperGodMode",
        "iat": now,
        "exp": now + 3600,
    }
    fake_role_token = jwt.encode(payload, settings.USER_JWT_SECRET, algorithm=settings.USER_JWT_ALGORITHM)

    with pytest.raises(AuthenticationError) as exc_info:
        verify_user_token(fake_role_token)
    assert exc_info.value.status_code == 401
    assert "unrecognized role" in exc_info.value.detail.lower()
