from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


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


def _mock_client_with_response(response):
    mock_client = MagicMock()
    mock_client.request.return_value = response
    return mock_client


def test_three_consecutive_failures_create_incident():
    endpoint = _create_endpoint()

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(_mock_failure())
        for _ in range(3):
            response = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert response.status_code == 201

    incidents_response = client.get(f"/endpoints/{endpoint['id']}/incidents")
    assert incidents_response.status_code == 200
    body = incidents_response.json()
    incidents = body["items"]
    assert len(incidents) == 1
    assert body["meta"]["total"] == 1
    assert incidents[0]["status"] == "open"
    assert incidents[0]["failure_count"] == 3
    assert incidents[0]["endpoint_id"] == endpoint["id"]
    assert incidents[0]["title"] == "Endpoint failure detected"
    assert incidents[0]["created_at"] is not None


def test_fourth_failure_increments_failure_count_no_duplicate():
    endpoint = _create_endpoint()

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(_mock_failure())
        for _ in range(4):
            response = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert response.status_code == 201

    incidents_response = client.get(f"/endpoints/{endpoint['id']}/incidents")
    assert incidents_response.status_code == 200
    body = incidents_response.json()
    incidents = body["items"]
    assert len(incidents) == 1
    assert body["meta"]["total"] == 1
    assert incidents[0]["status"] == "open"
    assert incidents[0]["failure_count"] == 4


def test_successful_check_resolves_open_incident():
    endpoint = _create_endpoint()

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(_mock_failure())
        for _ in range(3):
            response = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert response.status_code == 201

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(_mock_success())
        response = client.post(f"/endpoints/{endpoint['id']}/checks")
        assert response.status_code == 201

    incidents_response = client.get(f"/endpoints/{endpoint['id']}/incidents")
    assert incidents_response.status_code == 200
    body = incidents_response.json()
    incidents = body["items"]
    assert len(incidents) == 1
    assert body["meta"]["total"] == 1
    assert incidents[0]["status"] == "resolved"
    assert incidents[0]["resolved_at"] is not None


def test_non_consecutive_failures_do_not_create_incident():
    endpoint = _create_endpoint()

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(_mock_failure())
        response = client.post(f"/endpoints/{endpoint['id']}/checks")
        assert response.status_code == 201

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(_mock_success())
        response = client.post(f"/endpoints/{endpoint['id']}/checks")
        assert response.status_code == 201

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(_mock_failure())
        response = client.post(f"/endpoints/{endpoint['id']}/checks")
        assert response.status_code == 201

    incidents_response = client.get(f"/endpoints/{endpoint['id']}/incidents")
    assert incidents_response.status_code == 200
    body = incidents_response.json()
    incidents = body["items"]
    assert len(incidents) == 0
    assert body["meta"]["total"] == 0


def test_list_incidents_endpoint_not_found():
    response = client.get("/endpoints/999/incidents")
    assert response.status_code == 404
    assert response.json()["detail"] == "Endpoint not found"


def test_get_incident_by_id():
    endpoint = _create_endpoint()

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(_mock_failure())
        for _ in range(3):
            response = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert response.status_code == 201

    incidents_response = client.get(f"/endpoints/{endpoint['id']}/incidents")
    incident_id = incidents_response.json()["items"][0]["id"]

    response = client.get(f"/incidents/{incident_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == incident_id
    assert body["endpoint_id"] == endpoint["id"]


def test_get_incident_not_found():
    response = client.get("/incidents/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Incident not found"


def test_list_incidents_pagination_default_limit():
    endpoint = _create_endpoint()

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(_mock_failure())
        for _ in range(55):
            resp = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert resp.status_code == 201

    response = client.get(f"/endpoints/{endpoint['id']}/incidents")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1  # Only one open incident exists per endpoint
    assert body["meta"]["total"] == 1
    assert body["meta"]["limit"] == 50
    assert body["meta"]["offset"] == 0


def test_list_incidents_pagination_explicit_limit_offset():
    endpoint = _create_endpoint()

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(_mock_failure())
        for _ in range(3):
            resp = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert resp.status_code == 201

    response = client.get(f"/endpoints/{endpoint['id']}/incidents?limit=1&offset=0")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["meta"]["total"] == 1
    assert body["meta"]["limit"] == 1
    assert body["meta"]["offset"] == 0


def test_list_incidents_pagination_limit_zero_returns_422():
    endpoint = _create_endpoint()
    response = client.get(f"/endpoints/{endpoint['id']}/incidents?limit=0")
    assert response.status_code == 422


def test_list_incidents_pagination_limit_over_max_returns_422():
    endpoint = _create_endpoint()
    response = client.get(f"/endpoints/{endpoint['id']}/incidents?limit=300")
    assert response.status_code == 422


def test_list_incidents_pagination_offset_past_end():
    endpoint = _create_endpoint()

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(_mock_failure())
        for _ in range(3):
            resp = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert resp.status_code == 201

    response = client.get(f"/endpoints/{endpoint['id']}/incidents?offset=10")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["meta"]["total"] == 1
    assert body["meta"]["offset"] == 10
