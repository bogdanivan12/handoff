from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app


class _FakeSessionOk:
    async def execute(self, *args, **kwargs):
        return None


class _FakeSessionError:
    async def execute(self, *args, **kwargs):
        raise ConnectionError("db unreachable")


async def _override_ok() -> AsyncGenerator[_FakeSessionOk, None]:
    yield _FakeSessionOk()


async def _override_error() -> AsyncGenerator[_FakeSessionError, None]:
    yield _FakeSessionError()


def test_health_returns_ok_when_db_reachable():
    app.dependency_overrides[get_db] = _override_ok
    client = TestClient(app)
    response = client.get("/health")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "connected"}


def test_health_returns_error_when_db_unreachable():
    app.dependency_overrides[get_db] = _override_error
    client = TestClient(app)
    response = client.get("/health")
    app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "error"}
