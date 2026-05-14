from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from database import get_db
from main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["db"] == "ok"
    assert body["version"] != ""
    assert body["error"] is None


def test_health_degraded_when_db_fails():
    mock_db = MagicMock()
    mock_db.execute.side_effect = OperationalError(
        "SELECT 1", None, Exception("connection failed")
    )

    def bad_override():
        yield mock_db

    original = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = bad_override
    try:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["db"] == "error"
        assert body["error"] is not None
        assert body["version"] != ""
    finally:
        app.dependency_overrides[get_db] = original
