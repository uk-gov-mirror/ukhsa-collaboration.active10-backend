import time
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from docker.errors import DockerException
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import NullPool, create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from auth import auth_bearer
from db.session import Base, get_db_session
from main import app
from service.keycloak_userinfo_service import KeycloakUserInfoService

user_sub = "3a8d2869-0b2e-485a-9e67-8a906e6194ce"
invalid_token = "invalid-test-token"
authenticated_token = f"test-token-{user_sub}"

try:
    postgres = PostgresContainer("postgres:16")
    postgres.start()
except DockerException as exc:  # pragma: no cover - only exercised when docker unavailable
    pytest.skip(
        f"Docker not available for Postgres test container: {exc}",
        allow_module_level=True,
    )

engine = create_engine(postgres.get_connection_url(), poolclass=NullPool)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def db_engine():
    database_url = postgres.get_connection_url()

    alembic_cfg = Config()
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    alembic_cfg.set_main_option("script_location", "db/migrations")

    with engine.begin() as connection:
        alembic_cfg.attributes["connection"] = connection
        command.upgrade(alembic_cfg, "head")

    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    postgres.stop()


@pytest.fixture(scope="module")
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    yield session
    transaction.rollback()
    session.close()
    connection.close()


@pytest.fixture(scope="module")
def client(db_session):
    def override_get_db():
        yield db_session

    def override_keycloak_userinfo_service():
        class FakeKeycloakUserInfoService:
            def get_userinfo(self, access_token: str) -> dict[str, Any]:
                return {
                    "sub": user_sub,
                    "given_name": "Default",
                    "email": "default@example.com",
                    "identity_proofing_level": "P5",
                    "birthdate": "1990-01-01",
                }

        return FakeKeycloakUserInfoService()

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[KeycloakUserInfoService] = override_keycloak_userinfo_service

    with TestClient(app) as client:
        yield client


TOKEN_EXPIRY_5_MINUTES_AS_SEC = 300


def decode_test_jwt(token: str) -> dict:
    if token == authenticated_token:
        return {
            "sub": user_sub,
            "exp": time.time() + TOKEN_EXPIRY_5_MINUTES_AS_SEC,
        }
    raise HTTPException(status_code=403, detail="Token is not valid")


@pytest.fixture(scope="function")
def authenticated_user():
    auth_bearer.decode_jwt = decode_test_jwt
    return SimpleNamespace(id=user_sub, token=SimpleNamespace(token=authenticated_token))


@pytest.fixture(scope="function")
def unauthenticated_user():
    auth_bearer.decode_jwt = decode_test_jwt
    return SimpleNamespace(id="invalid-user", token=SimpleNamespace(token=invalid_token))


@contextmanager
def override_get_db_context_session(db_session):
    yield db_session
