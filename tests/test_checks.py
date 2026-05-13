import time
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def _create_endpoint():
    response = client.post(
        "/endpoints",
        json={
            "name": "Test API",
            "url": "https://example.com/api",
            "expected_status_code": 200,
            "timeout_seconds": 3.0,
        },
    )
    assert response.status_code == 201
    return response.json()


@patch("checks.httpx.Client.get")
def test_check_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    endpoint = _create_endpoint()
    response = client.post(f"/endpoints/{endpoint['id']}/checks")

    assert response.status_code == 201
    body = response.json()
    assert body["endpoint_id"] == endpoint["id"]
    assert body["url"] == "https://example.com/api"
    assert body["expected_status_code"] == 200
    assert body["actual_status_code"] == 200
    assert body["success"] is True
    assert body["error_message"] is None
    assert body["response_time_ms"] is not None
    assert body["checked_at"] is not None
    assert body["id"] is not None


@patch("checks.httpx.Client.get")
def test_check_status_mismatch(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_get.return_value = mock_response

    endpoint = _create_endpoint()
    response = client.post(f"/endpoints/{endpoint['id']}/checks")

    assert response.status_code == 201
    body = response.json()
    assert body["actual_status_code"] == 500
    assert body["success"] is False
    assert body["error_message"] is None


@patch("checks.httpx.Client.get")
def test_check_timeout(mock_get):
    mock_get.side_effect = httpx.TimeoutException("Request timed out")

    endpoint = _create_endpoint()
    response = client.post(f"/endpoints/{endpoint['id']}/checks")

    assert response.status_code == 201
    body = response.json()
    assert body["actual_status_code"] is None
    assert body["success"] is False
    assert "Request timed out" in body["error_message"]
    assert body["response_time_ms"] is not None


@patch("checks.httpx.Client.get")
def test_check_connect_error(mock_get):
    mock_get.side_effect = httpx.ConnectError("Connection failed")

    endpoint = _create_endpoint()
    response = client.post(f"/endpoints/{endpoint['id']}/checks")

    assert response.status_code == 201
    body = response.json()
    assert body["actual_status_code"] is None
    assert body["success"] is False
    assert "Connection failed" in body["error_message"]
    assert body["response_time_ms"] is not None


def test_check_endpoint_not_found():
    response = client.post("/endpoints/999/checks")
    assert response.status_code == 404
    assert response.json()["detail"] == "Endpoint not found"


def test_list_checks_empty():
    endpoint = _create_endpoint()
    response = client.get(f"/endpoints/{endpoint['id']}/checks")
    assert response.status_code == 200
    assert response.json() == []


def test_list_checks_ordered_and_filtered_by_endpoint():
    endpoint_a = _create_endpoint()
    endpoint_b = client.post(
        "/endpoints",
        json={
            "name": "Other API",
            "url": "https://other.example.com/api",
            "expected_status_code": 200,
            "timeout_seconds": 3.0,
        },
    )
    assert endpoint_b.status_code == 201
    endpoint_b = endpoint_b.json()

    mock_response = MagicMock()
    mock_response.status_code = 200

    # Trigger checks for endpoint A with small delays for distinct timestamps
    with patch("checks.httpx.Client.get", return_value=mock_response):
        response_a1 = client.post(f"/endpoints/{endpoint_a['id']}/checks")
        assert response_a1.status_code == 201
    time.sleep(0.01)
    with patch("checks.httpx.Client.get", return_value=mock_response):
        response_a2 = client.post(f"/endpoints/{endpoint_a['id']}/checks")
        assert response_a2.status_code == 201
    time.sleep(0.01)
    with patch("checks.httpx.Client.get", return_value=mock_response):
        response_a3 = client.post(f"/endpoints/{endpoint_a['id']}/checks")
        assert response_a3.status_code == 201

    # Trigger a check for endpoint B
    with patch("checks.httpx.Client.get", return_value=mock_response):
        response_b1 = client.post(f"/endpoints/{endpoint_b['id']}/checks")
        assert response_b1.status_code == 201

    response = client.get(f"/endpoints/{endpoint_a['id']}/checks")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3

    checked_ats = [item["checked_at"] for item in body]
    assert checked_ats == sorted(checked_ats, reverse=True)

    for item in body:
        assert item["endpoint_id"] == endpoint_a["id"]


def test_list_checks_endpoint_not_found():
    response = client.get("/endpoints/999/checks")
    assert response.status_code == 404
    assert response.json()["detail"] == "Endpoint not found"
