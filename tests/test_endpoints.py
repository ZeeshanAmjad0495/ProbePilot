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
    assert body["method"] == "GET"
    assert body["request_headers"] is None
    assert body["request_body"] is None


def test_create_endpoint_with_custom_http_fields():
    response = client.post(
        "/endpoints",
        json={
            "name": "Test API",
            "url": "https://example.com/api",
            "method": "POST",
            "request_headers": {"Content-Type": "application/json"},
            "request_body": '{"key": "value"}',
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["method"] == "POST"
    assert body["request_headers"] == {"Content-Type": "application/json"}
    assert body["request_body"] == '{"key": "value"}'


def test_create_endpoint_invalid_method():
    response = client.post(
        "/endpoints",
        json={
            "name": "Test API",
            "url": "https://example.com/api",
            "method": "INVALID",
        },
    )
    assert response.status_code == 422


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


def test_update_endpoint_custom_http_fields():
    create_response = client.post(
        "/endpoints",
        json={"name": "Old Name", "url": "https://old.example.com"},
    )
    endpoint_id = create_response.json()["id"]

    response = client.put(
        f"/endpoints/{endpoint_id}",
        json={
            "method": "PATCH",
            "request_headers": {"X-Custom": "header"},
            "request_body": "patch body",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "PATCH"
    assert body["request_headers"] == {"X-Custom": "header"}
    assert body["request_body"] == "patch body"


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


def test_list_endpoints_search_by_name():
    client.post("/endpoints", json={"name": "Alpha Service", "url": "https://alpha.com"})
    client.post("/endpoints", json={"name": "Beta Service", "url": "https://beta.com"})

    response = client.get("/endpoints?q=Alpha")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == "Alpha Service"
    assert body["meta"]["total"] == 1


def test_list_endpoints_search_by_url():
    client.post("/endpoints", json={"name": "Alpha", "url": "https://alpha.example.com"})
    client.post("/endpoints", json={"name": "Beta", "url": "https://beta.other.com"})

    response = client.get("/endpoints?q=example")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["url"] == "https://alpha.example.com/"
    assert body["meta"]["total"] == 1


def test_list_endpoints_search_case_insensitive():
    client.post("/endpoints", json={"name": "Alpha Service", "url": "https://alpha.com"})

    response = client.get("/endpoints?q=alpha")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == "Alpha Service"


def test_list_endpoints_search_no_matches():
    client.post("/endpoints", json={"name": "Alpha", "url": "https://alpha.com"})

    response = client.get("/endpoints?q=nonexistent")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["meta"]["total"] == 0


def test_list_endpoints_search_with_pagination():
    client.post("/endpoints", json={"name": "Alpha One", "url": "https://a1.com"})
    client.post("/endpoints", json={"name": "Alpha Two", "url": "https://a2.com"})
    client.post("/endpoints", json={"name": "Alpha Three", "url": "https://a3.com"})
    client.post("/endpoints", json={"name": "Beta", "url": "https://beta.com"})

    response = client.get("/endpoints?q=Alpha&limit=2&offset=1")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["meta"]["total"] == 3
    assert body["meta"]["limit"] == 2
    assert body["meta"]["offset"] == 1


def test_list_endpoints_search_empty_q_returns_422():
    response = client.get("/endpoints?q=")
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
    assert len(list_response.json()["items"]) == 1

    # Verify via update
    update_response = client.put(
        f"/endpoints/{endpoint_id}",
        json={"name": "Persist Updated"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Persist Updated"
