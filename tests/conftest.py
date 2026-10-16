"""Shared test fixtures.

Every test gets its own empty in-memory database, so tests never touch
the real shortener.db file and never affect each other.
"""

from collections.abc import Iterator

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import security
from app.database import Base, get_db, get_session_factory
from app.main import app
from app.models import User  # importing the models also registers the tables
from app.rate_limit import limiter
from app.services import user_service
from tests.sample_users import OTHER_EMAIL, OWNER_EMAIL, PASSWORD


@pytest.fixture(autouse=True)
def cheap_password_hasher(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use light Argon2 settings in tests, so the test suite stays fast.

    Real hashing is slow on purpose (about 0.2 seconds each). The app itself
    keeps the strong default settings.
    """
    monkeypatch.setattr(
        security,
        "_password_hasher",
        PasswordHasher(time_cost=1, memory_cost=8, parallelism=1),
    )


@pytest.fixture(autouse=True)
def rate_limits_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Switch rate limiting off, so tests can make many requests.

    Tests that check the limits use the `rate_limits_on` fixture.
    """
    monkeypatch.setattr(limiter, "enabled", False)


@pytest.fixture
def rate_limits_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Switch rate limiting on, with empty counters."""
    monkeypatch.setattr(limiter, "enabled", True)
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    """A factory that opens sessions on a fresh in-memory SQLite database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # keep one connection so the data stays alive
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def db_session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """One session on the test database. Tests use it to look at saved data."""
    with session_factory() as session:
        yield session


@pytest.fixture
def client(
    db_session: Session, session_factory: sessionmaker[Session]
) -> Iterator[TestClient]:
    """A test client that is NOT logged in. Its app uses the in-memory database.

    Both the request session and the background-task sessions point to
    the test database.
    """

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def user(db_session: Session) -> User:
    """A registered user."""
    return user_service.register_user(db_session, OWNER_EMAIL, PASSWORD)


@pytest.fixture
def other_user(db_session: Session) -> User:
    """A second registered user, for tests about who may see what."""
    return user_service.register_user(db_session, OTHER_EMAIL, PASSWORD)


@pytest.fixture
def auth_headers(user: User) -> dict[str, str]:
    """The Authorization header of the `user` fixture."""
    token = security.create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_client(client: TestClient, auth_headers: dict[str, str]) -> TestClient:
    """A test client that is logged in as the `user` fixture.

    It is a second client on the same app, so a test can use both
    `client` (logged out) and `auth_client` (logged in).
    """
    return TestClient(app, headers=auth_headers)
