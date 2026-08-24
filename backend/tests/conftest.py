"""
Shared pytest fixtures for the Category 6/7/11 zero-Okta-traffic test suite.

Design:
  - A dedicated in-memory SQLite database is used for every test. It is
    never the real intelliid.db, and its schema is dropped/recreated
    before *and* after every single test (not just via transaction
    rollback), because application code under test calls db.commit()
    directly, which would otherwise leak state across tests.
  - app.db.database.get_db is overridden (via FastAPI's
    dependency_overrides) to hand out sessions bound to that test
    database instead of the real one.
  - The module-level `user_service` / `group_service` singletons in
    app.services.lifecycle_execution_service are monkeypatched with
    AsyncMock objects that mimic the real UserService/GroupService
    method contracts, so no code path under test can produce live
    Okta traffic.
  - As a second line of defense, OktaClient.request itself is patched
    to raise if it is ever invoked, so even a code path that bypasses
    the singleton mocks (e.g. a router that builds its own
    UserService()) cannot reach the network.
"""

import pytest
from unittest.mock import AsyncMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi.testclient import TestClient

from app.db.database import Base, get_db
from app.services import lifecycle_execution_service
from app.services import impact_service
from app.services.okta_client import OktaClient


TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def _override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def reset_test_database():
    """
    Explicitly drop and recreate every table before AND after each test.
    Application code commits directly against the session, so relying
    on transaction rollback alone would not give test isolation.
    """

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def block_live_okta_calls(monkeypatch):
    """
    Belt-and-suspenders guard: even if a test (or the code under test)
    reaches an unmocked OktaClient instance, any attempt to actually
    call out to Okta fails loudly instead of making network traffic.
    """

    async def _forbidden_request(self, method, endpoint, **kwargs):
        raise AssertionError(
            "OktaClient.request() was called during a test - live Okta "
            f"traffic is forbidden in this suite (method={method}, "
            f"endpoint={endpoint})"
        )

    monkeypatch.setattr(OktaClient, "request", _forbidden_request)

    yield


def _make_user_service_mock():
    """
    AsyncMock shaped like app.services.user_service.UserService, with
    default return values matching the real Okta response shapes that
    method returns to its caller (see user_service.py).
    """

    mock = AsyncMock(name="MockUserService")

    mock.list_users.return_value = []

    mock.create_user.return_value = {
        "id": "00uMockCreatedUser",
        "status": "STAGED",
        "profile": {
            "firstName": "Mock",
            "lastName": "User",
            "email": "mock.user@example.com",
            "login": "mock.user@example.com",
        },
    }

    mock.provision_user.return_value = {
        "id": "00uMockProvisionedUser",
        "status": "PROVISIONED",
    }

    # Real OktaClient.request() returns None on a 204 No Content,
    # which is what deactivate/delete lifecycle calls return.
    mock.deactivate_user.return_value = None

    mock.delete_user.return_value = None

    mock.bulk_deactivate.return_value = {
        "total": 0,
        "successful": 0,
        "failed": 0,
        "results": [],
    }

    return mock


def _make_group_service_mock():
    """
    AsyncMock shaped like app.services.group_service.GroupService.
    """

    mock = AsyncMock(name="MockGroupService")

    mock.move_user.return_value = {
        "user_id": "00uMockUser",
        "old_group": "grpMockOld",
        "new_group": "grpMockNew",
    }

    return mock


@pytest.fixture(autouse=True)
def mock_okta_backed_services(monkeypatch):
    """
    Replaces the module-level user_service/group_service singletons
    used by lifecycle_execution_service with mocks, for every test.
    Yields (user_service_mock, group_service_mock) so individual tests
    can override return values for their scenario.
    """

    user_mock = _make_user_service_mock()
    group_mock = _make_group_service_mock()

    monkeypatch.setattr(lifecycle_execution_service, "user_service", user_mock)
    monkeypatch.setattr(lifecycle_execution_service, "group_service", group_mock)

    yield user_mock, group_mock


@pytest.fixture(autouse=True)
def mock_impact_service_okta_calls(monkeypatch):
    """
    impact_service (Category 7 access-preview engine) keeps its own
    user_service/group_service singletons, separate from the ones
    lifecycle_execution_service uses above. Default them to empty
    results here so every dry-run in the suite gets a real (but
    no-op) impact_decision unless a test overrides these mocks for
    its own access-preview scenario - see test_lifecycle.py's
    _mock_impact_services() helper.
    """

    group_mock = AsyncMock(name="MockImpactGroupService")
    user_mock = AsyncMock(name="MockImpactUserService")

    group_mock.list_apps.return_value = []
    user_mock.list_user_groups.return_value = []

    monkeypatch.setattr(impact_service, "group_service", group_mock)
    monkeypatch.setattr(impact_service, "user_service", user_mock)

    yield group_mock, user_mock


@pytest.fixture
def client():
    from app.main import app

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def db_session():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()
