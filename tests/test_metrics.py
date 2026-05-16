from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _create_endpoint(name="Test API", url="https://example.com/api"):
    response = client.post(
        "/endpoints",
        json={
            "name": name,
            "url": url,
            "expected_status_code": 200,
            "timeout_seconds": 3.0,
        },
    )
    assert response.status_code == 201
    return response.json()


def _mock_success():
    mock = MagicMock()
    mock.status_code = 200
    return mock


def _mock_failure():
    mock = MagicMock()
    mock.status_code = 500
    return mock


def _mock_client_with_response(response):
    mock_client = MagicMock()
    mock_client.request.return_value = response
    return mock_client


def test_metrics_empty():
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["total_endpoints"] == 0
    assert body["endpoints_up"] == 0
    assert body["endpoints_down"] == 0
    assert body["open_incidents"] == 0
    assert body["resolved_incidents"] == 0


def test_metrics_with_endpoints_no_checks():
    _create_endpoint("API 1", "https://api1.com")
    _create_endpoint("API 2", "https://api2.com")

    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["total_endpoints"] == 2
    assert body["endpoints_up"] == 0
    assert body["endpoints_down"] == 0
    assert body["open_incidents"] == 0
    assert body["resolved_incidents"] == 0


def test_metrics_with_mixed_checks():
    ep1 = _create_endpoint("API 1", "https://api1.com")
    ep2 = _create_endpoint("API 2", "https://api2.com")

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(
            _mock_success()
        )
        client.post(f"/endpoints/{ep1['id']}/checks")

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(
            _mock_failure()
        )
        for _ in range(3):
            client.post(f"/endpoints/{ep2['id']}/checks")

    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["total_endpoints"] == 2
    assert body["endpoints_up"] == 1
    assert body["endpoints_down"] == 1
    assert body["open_incidents"] == 1
    assert body["resolved_incidents"] == 0


def test_metrics_latest_check_per_endpoint():
    ep1 = _create_endpoint("API 1", "https://api1.com")

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(
            _mock_success()
        )
        client.post(f"/endpoints/{ep1['id']}/checks")

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(
            _mock_failure()
        )
        client.post(f"/endpoints/{ep1['id']}/checks")

    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["total_endpoints"] == 1
    assert body["endpoints_up"] == 0
    assert body["endpoints_down"] == 1
    assert body["open_incidents"] == 0
    assert body["resolved_incidents"] == 0


def test_metrics_resolved_incident():
    ep1 = _create_endpoint("API 1", "https://api1.com")

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(
            _mock_failure()
        )
        for _ in range(3):
            client.post(f"/endpoints/{ep1['id']}/checks")

    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_client_with_response(
            _mock_success()
        )
        client.post(f"/endpoints/{ep1['id']}/checks")

    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["total_endpoints"] == 1
    assert body["endpoints_up"] == 1
    assert body["endpoints_down"] == 0
    assert body["open_incidents"] == 0
    assert body["resolved_incidents"] == 1
