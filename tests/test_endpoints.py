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


def test_create_endpoint():
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
    body = response.json()
    assert body["id"] is not None
    assert body["name"] == "Test API"
    assert body["url"] == "https://example.com/api"
    assert body["expected_status_code"] == 200
    assert body["timeout_seconds"] == 3.0
    assert "created_at" in body


def test_create_endpoint_defaults():
    response = client.post(
        "/endpoints",
        json={"name": "Test API", "url": "https://example.com/api"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["expected_status_code"] == 200
    assert body["timeout_seconds"] == 5.0


def test_list_endpoints():
    client.post(
        "/endpoints",
        json={"name": "First", "url": "https://first.example.com"},
    )
    client.post(
        "/endpoints",
        json={"name": "Second", "url": "https://second.example.com"},
    )

    response = client.get("/endpoints")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["name"] == "First"
    assert body[1]["name"] == "Second"


def test_get_endpoint():
    create_response = client.post(
        "/endpoints",
        json={"name": "Test API", "url": "https://example.com/api"},
    )
    endpoint_id = create_response.json()["id"]

    response = client.get(f"/endpoints/{endpoint_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == endpoint_id
    assert body["name"] == "Test API"


def test_get_endpoint_not_found():
    response = client.get("/endpoints/999")
    assert response.status_code == 404


def test_update_endpoint():
    create_response = client.post(
        "/endpoints",
        json={"name": "Old Name", "url": "https://old.example.com"},
    )
    endpoint_id = create_response.json()["id"]

    response = client.put(
        f"/endpoints/{endpoint_id}",
        json={
            "name": "New Name",
            "url": "https://new.example.com",
            "expected_status_code": 201,
            "timeout_seconds": 10.0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == endpoint_id
    assert body["name"] == "New Name"
    assert body["url"] == "https://new.example.com/"
    assert body["expected_status_code"] == 201
    assert body["timeout_seconds"] == 10.0


def test_update_endpoint_not_found():
    response = client.put(
        "/endpoints/999",
        json={"name": "New Name"},
    )
    assert response.status_code == 404


def test_create_endpoint_invalid_empty_name():
    response = client.post(
        "/endpoints",
        json={"name": "", "url": "https://example.com/api"},
    )
    assert response.status_code == 422


def test_create_endpoint_invalid_url():
    response = client.post(
        "/endpoints",
        json={"name": "Test", "url": "not-a-url"},
    )
    assert response.status_code == 422


def test_create_endpoint_invalid_negative_timeout():
    response = client.post(
        "/endpoints",
        json={
            "name": "Test",
            "url": "https://example.com/api",
            "timeout_seconds": -1.0,
        },
    )
    assert response.status_code == 422


def test_persistence_across_requests():
    create_response = client.post(
        "/endpoints",
        json={"name": "Persist", "url": "https://persist.example.com"},
    )
    endpoint_id = create_response.json()["id"]

    # Verify via get
    get_response = client.get(f"/endpoints/{endpoint_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Persist"

    # Verify via list
    list_response = client.get("/endpoints")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    # Verify via update
    update_response = client.put(
        f"/endpoints/{endpoint_id}",
        json={"name": "Persist Updated"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Persist Updated"
