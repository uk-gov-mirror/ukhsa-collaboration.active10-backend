import time
from contextlib import contextmanager
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from docker.errors import DockerException
from fastapi.testclient import TestClient
from sqlalchemy import NullPool, create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from auth import auth_bearer
from crud.user_crud import UserCRUD
from db.session import Base, get_db_session
from main import app
from models import User, UserToken

user_uuid_pk = uuid4()

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

    user_crud = UserCRUD(session)
    default_user = User(
        id=user_uuid_pk,
        unique_id="3a8d2869-0b2e-485a-9e67-8a906e6194ce",
        nhs_number="1234567890",
        first_name="Default",
        email="default@example.com",
        gender="male",
        postcode="12345",
        identity_level="1",
        date_of_birth="1990-01-01",
    )
    if not session.query(User).filter_by(id=user_uuid_pk).first():
        _ = user_crud.create_user(default_user)

    yield session
    transaction.rollback()
    session.close()
    connection.close()


@pytest.fixture(scope="module")
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db

    with TestClient(app) as client:
        yield client


TOKEN_EXPIRY_5_MINUTES_AS_SEC = 300


def create_user_token(user, db_session, is_authenticated=True) -> None:
    if user.token:
        db_session.delete(user.token)
        db_session.commit()

    subject = user.unique_id if is_authenticated else str(uuid4())
    token = f"test-token-{subject}"

    user_token = UserToken(user_id=user.id, token=token)
    db_session.add(user_token)
    db_session.commit()
    db_session.refresh(user)


@pytest.fixture(scope="function")
def authenticated_user(db_session):
    user = db_session.query(User).filter(User.id == user_uuid_pk).first()
    create_user_token(user, db_session, is_authenticated=True)
    auth_bearer.decode_jwt = lambda _: {
        "sub": str(user.id),
        "exp": time.time() + TOKEN_EXPIRY_5_MINUTES_AS_SEC,
    }
    return user


@pytest.fixture(scope="function")
def unauthenticated_user(db_session):
    user = db_session.query(User).filter(User.id == user_uuid_pk).first()
    missing_subject = str(uuid4())
    create_user_token(user, db_session, is_authenticated=False)
    auth_bearer.decode_jwt = lambda _: {
        "sub": missing_subject,
        "exp": time.time() + TOKEN_EXPIRY_5_MINUTES_AS_SEC,
    }
    return user


@contextmanager
def override_get_db_context_session(db_session):
    yield db_session
