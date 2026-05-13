from unittest.mock import MagicMock, patch

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


def _mock_failure():
    mock = MagicMock()
    mock.status_code = 500
    return mock


def _mock_success():
    mock = MagicMock()
    mock.status_code = 200
    return mock


def test_three_consecutive_failures_create_incident():
    endpoint = _create_endpoint()

    with patch("checks.httpx.Client.get", return_value=_mock_failure()):
        for _ in range(3):
            response = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert response.status_code == 201

    incidents_response = client.get(f"/endpoints/{endpoint['id']}/incidents")
    assert incidents_response.status_code == 200
    incidents = incidents_response.json()
    assert len(incidents) == 1
    assert incidents[0]["status"] == "open"
    assert incidents[0]["failure_count"] == 3
    assert incidents[0]["endpoint_id"] == endpoint["id"]
    assert incidents[0]["title"] == "Endpoint failure detected"
    assert incidents[0]["created_at"] is not None


def test_fourth_failure_increments_failure_count_no_duplicate():
    endpoint = _create_endpoint()

    with patch("checks.httpx.Client.get", return_value=_mock_failure()):
        for _ in range(4):
            response = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert response.status_code == 201

    incidents_response = client.get(f"/endpoints/{endpoint['id']}/incidents")
    assert incidents_response.status_code == 200
    incidents = incidents_response.json()
    assert len(incidents) == 1
    assert incidents[0]["status"] == "open"
    assert incidents[0]["failure_count"] == 4


def test_successful_check_resolves_open_incident():
    endpoint = _create_endpoint()

    with patch("checks.httpx.Client.get", return_value=_mock_failure()):
        for _ in range(3):
            response = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert response.status_code == 201

    with patch("checks.httpx.Client.get", return_value=_mock_success()):
        response = client.post(f"/endpoints/{endpoint['id']}/checks")
        assert response.status_code == 201

    incidents_response = client.get(f"/endpoints/{endpoint['id']}/incidents")
    assert incidents_response.status_code == 200
    incidents = incidents_response.json()
    assert len(incidents) == 1
    assert incidents[0]["status"] == "resolved"
    assert incidents[0]["resolved_at"] is not None


def test_non_consecutive_failures_do_not_create_incident():
    endpoint = _create_endpoint()

    with patch("checks.httpx.Client.get", return_value=_mock_failure()):
        response = client.post(f"/endpoints/{endpoint['id']}/checks")
        assert response.status_code == 201

    with patch("checks.httpx.Client.get", return_value=_mock_success()):
        response = client.post(f"/endpoints/{endpoint['id']}/checks")
        assert response.status_code == 201

    with patch("checks.httpx.Client.get", return_value=_mock_failure()):
        response = client.post(f"/endpoints/{endpoint['id']}/checks")
        assert response.status_code == 201

    incidents_response = client.get(f"/endpoints/{endpoint['id']}/incidents")
    assert incidents_response.status_code == 200
    incidents = incidents_response.json()
    assert len(incidents) == 0


def test_list_incidents_endpoint_not_found():
    response = client.get("/endpoints/999/incidents")
    assert response.status_code == 404
    assert response.json()["detail"] == "Endpoint not found"


def test_get_incident_by_id():
    endpoint = _create_endpoint()

    with patch("checks.httpx.Client.get", return_value=_mock_failure()):
        for _ in range(3):
            response = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert response.status_code == 201

    incidents_response = client.get(f"/endpoints/{endpoint['id']}/incidents")
    incident_id = incidents_response.json()[0]["id"]

    response = client.get(f"/incidents/{incident_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == incident_id
    assert body["endpoint_id"] == endpoint["id"]


def test_get_incident_not_found():
    response = client.get("/incidents/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Incident not found"
