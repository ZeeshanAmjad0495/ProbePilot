from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


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
    assert len(body["items"]) == 2
    assert body["items"][0]["name"] == "First"
    assert body["items"][1]["name"] == "Second"
    assert body["meta"]["total"] == 2
    assert body["meta"]["limit"] == 50
    assert body["meta"]["offset"] == 0


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


def test_list_endpoints_pagination_default_limit():
    for i in range(55):
        client.post(
            "/endpoints",
            json={"name": f"Endpoint {i}", "url": f"https://example{i}.com"},
        )

    response = client.get("/endpoints")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 50
    assert body["meta"]["total"] == 55
    assert body["meta"]["limit"] == 50
    assert body["meta"]["offset"] == 0


def test_list_endpoints_pagination_explicit_limit_offset():
    for i in range(5):
        client.post(
            "/endpoints",
            json={"name": f"Endpoint {i}", "url": f"https://example{i}.com"},
        )

    response = client.get("/endpoints?limit=2&offset=1")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["name"] == "Endpoint 1"
    assert body["meta"]["total"] == 5
    assert body["meta"]["limit"] == 2
    assert body["meta"]["offset"] == 1


def test_list_endpoints_pagination_limit_zero_returns_422():
    response = client.get("/endpoints?limit=0")
    assert response.status_code == 422


def test_list_endpoints_pagination_limit_over_max_returns_422():
    response = client.get("/endpoints?limit=300")
    assert response.status_code == 422


def test_list_endpoints_pagination_offset_past_end():
    client.post(
        "/endpoints",
        json={"name": "Only", "url": "https://only.example.com"},
    )

    response = client.get("/endpoints?offset=10")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["meta"]["total"] == 1
    assert body["meta"]["offset"] == 10


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
    assert len(list_response.json()["items"]) == 1

    # Verify via update
    update_response = client.put(
        f"/endpoints/{endpoint_id}",
        json={"name": "Persist Updated"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Persist Updated"
