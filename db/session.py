from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from utils.base_config import config

DATABASE_URL = f"postgresql+psycopg://{config.db_user}:{config.db_pass}@{config.db_host}:{config.db_port}/{config.db_name}"

Engine = create_engine(
    DATABASE_URL,
    pool_size=config.db_pool_size,
    max_overflow=config.db_max_overflow,
    pool_recycle=config.db_pool_recycle,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=Engine)

Base = declarative_base()


@contextmanager
def get_db_context_session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
