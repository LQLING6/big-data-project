import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.seed import DEMO_CREDENTIALS, seed_demo


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    seed_demo(factory)
    yield factory
    engine.dispose()


@pytest.fixture
def client(session_factory):
    def override_db():
        with session_factory() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def student_headers(client):
    result = client.post("/api/v1/auth/login", json={"username": "student", "password": DEMO_CREDENTIALS["student"]})
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


@pytest.fixture
def admin_headers(client):
    result = client.post("/api/v1/auth/login", json={"username": "admin", "password": DEMO_CREDENTIALS["admin"]})
    return {"Authorization": f"Bearer {result.json()['access_token']}"}
