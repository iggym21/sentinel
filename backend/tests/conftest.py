import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base


@pytest.fixture()
def db_session():
    # StaticPool keeps a single shared connection alive across threads for
    # the lifetime of this engine. Without it, SQLAlchemy's default pool
    # for "sqlite:///:memory:" hands out a fresh (and separately empty)
    # in-memory database per thread — harmless for tests that only ever
    # touch the session from one thread, but FastAPI's TestClient runs
    # sync route handlers in a worker thread (Task 14's test_api.py), so
    # without StaticPool those requests see "no such table" against an
    # empty database that isn't the one `create_all` populated here.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
