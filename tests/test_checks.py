import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from checks import _evaluate_incidents
from main import app
from models import Check

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


@patch("checks.httpx.Client")
def test_check_success(mock_client_class):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

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

    mock_client.request.assert_called_once()
    call_args = mock_client.request.call_args
    assert call_args[0][0] == "GET"
    assert call_args[1]["headers"] is None
    assert call_args[1]["content"] is None


@patch("checks.httpx.Client")
def test_check_status_mismatch(mock_client_class):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    endpoint = _create_endpoint()
    response = client.post(f"/endpoints/{endpoint['id']}/checks")

    assert response.status_code == 201
    body = response.json()
    assert body["actual_status_code"] == 500
    assert body["success"] is False
    assert body["error_message"] is None


@patch("checks.httpx.Client")
def test_check_timeout(mock_client_class):
    mock_client = MagicMock()
    mock_client.request.side_effect = httpx.TimeoutException("Request timed out")
    mock_client_class.return_value.__enter__.return_value = mock_client

    endpoint = _create_endpoint()
    response = client.post(f"/endpoints/{endpoint['id']}/checks")

    assert response.status_code == 201
    body = response.json()
    assert body["actual_status_code"] is None
    assert body["success"] is False
    assert "Request timed out" in body["error_message"]
    assert body["response_time_ms"] is not None


@patch("checks.httpx.Client")
def test_check_connect_error(mock_client_class):
    mock_client = MagicMock()
    mock_client.request.side_effect = httpx.ConnectError("Connection failed")
    mock_client_class.return_value.__enter__.return_value = mock_client

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
    body = response.json()
    assert body["items"] == []
    assert body["meta"]["total"] == 0
    assert body["meta"]["limit"] == 50
    assert body["meta"]["offset"] == 0


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

    def _mock_check_client():
        mock_client = MagicMock()
        mock_client.request.return_value = mock_response
        return mock_client

    # Trigger checks for endpoint A with small delays for distinct timestamps
    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_check_client()
        response_a1 = client.post(f"/endpoints/{endpoint_a['id']}/checks")
        assert response_a1.status_code == 201
    time.sleep(0.01)
    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_check_client()
        response_a2 = client.post(f"/endpoints/{endpoint_a['id']}/checks")
        assert response_a2.status_code == 201
    time.sleep(0.01)
    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_check_client()
        response_a3 = client.post(f"/endpoints/{endpoint_a['id']}/checks")
        assert response_a3.status_code == 201

    # Trigger a check for endpoint B
    with patch("checks.httpx.Client") as mock_class:
        mock_class.return_value.__enter__.return_value = _mock_check_client()
        response_b1 = client.post(f"/endpoints/{endpoint_b['id']}/checks")
        assert response_b1.status_code == 201

    response = client.get(f"/endpoints/{endpoint_a['id']}/checks")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 3
    assert body["meta"]["total"] == 3

    checked_ats = [item["checked_at"] for item in body["items"]]
    assert checked_ats == sorted(checked_ats, reverse=True)

    for item in body["items"]:
        assert item["endpoint_id"] == endpoint_a["id"]


def test_list_checks_endpoint_not_found():
    response = client.get("/endpoints/999/checks")
    assert response.status_code == 404
    assert response.json()["detail"] == "Endpoint not found"


def test_evaluate_incidents_catches_integrity_error():
    """Simulate a race where the open-incident query returns None but the
    flush fails because another transaction inserted the row first.
    """
    mock_db = MagicMock()

    check_query = MagicMock()
    check_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        MagicMock(success=False),
        MagicMock(success=False),
        MagicMock(success=False),
    ]

    existing_incident = MagicMock()
    existing_incident.failure_count = 3

    incident_query = MagicMock()
    incident_query.filter.return_value.first.side_effect = [None, existing_incident]

    def query_side_effect(model):
        if model is Check:
            return check_query
        return incident_query

    mock_db.query.side_effect = query_side_effect
    mock_db.flush.side_effect = IntegrityError("mock", "mock", Exception("duplicate"))

    _evaluate_incidents(mock_db, endpoint_id=1, success=False)

    mock_db.rollback.assert_called_once()
    assert existing_incident.failure_count == 4


def test_list_checks_pagination_default_limit():
    endpoint = _create_endpoint()
    mock_response = MagicMock()
    mock_response.status_code = 200

    for _ in range(55):
        with patch("checks.httpx.Client") as mock_class:
            mock_client = MagicMock()
            mock_client.request.return_value = mock_response
            mock_class.return_value.__enter__.return_value = mock_client
            resp = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert resp.status_code == 201

    response = client.get(f"/endpoints/{endpoint['id']}/checks")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 50
    assert body["meta"]["total"] == 55
    assert body["meta"]["limit"] == 50
    assert body["meta"]["offset"] == 0


def test_list_checks_pagination_explicit_limit_offset():
    endpoint = _create_endpoint()
    mock_response = MagicMock()
    mock_response.status_code = 200

    for _ in range(5):
        with patch("checks.httpx.Client") as mock_class:
            mock_client = MagicMock()
            mock_client.request.return_value = mock_response
            mock_class.return_value.__enter__.return_value = mock_client
            resp = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert resp.status_code == 201

    response = client.get(f"/endpoints/{endpoint['id']}/checks?limit=2&offset=1")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["meta"]["total"] == 5
    assert body["meta"]["limit"] == 2
    assert body["meta"]["offset"] == 1


def test_list_checks_pagination_limit_zero_returns_422():
    endpoint = _create_endpoint()
    response = client.get(f"/endpoints/{endpoint['id']}/checks?limit=0")
    assert response.status_code == 422


def test_list_checks_pagination_limit_over_max_returns_422():
    endpoint = _create_endpoint()
    response = client.get(f"/endpoints/{endpoint['id']}/checks?limit=300")
    assert response.status_code == 422


def test_list_checks_pagination_offset_past_end():
    endpoint = _create_endpoint()
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("checks.httpx.Client") as mock_class:
        mock_client = MagicMock()
        mock_client.request.return_value = mock_response
        mock_class.return_value.__enter__.return_value = mock_client
        resp = client.post(f"/endpoints/{endpoint['id']}/checks")
        assert resp.status_code == 201

    response = client.get(f"/endpoints/{endpoint['id']}/checks?offset=10")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["meta"]["total"] == 1
    assert body["meta"]["offset"] == 10


@patch("checks.httpx.Client")
def test_check_post_with_body(mock_client_class):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    create_resp = client.post(
        "/endpoints",
        json={
            "name": "POST API",
            "url": "https://example.com/api",
            "expected_status_code": 201,
            "method": "POST",
            "request_headers": {"Content-Type": "application/json"},
            "request_body": '{"key": "value"}',
        },
    )
    assert create_resp.status_code == 201
    endpoint = create_resp.json()
    assert endpoint["method"] == "POST"
    assert endpoint["request_headers"] == {"Content-Type": "application/json"}
    assert endpoint["request_body"] == '{"key": "value"}'

    response = client.post(f"/endpoints/{endpoint['id']}/checks")
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["actual_status_code"] == 201

    mock_client.request.assert_called_once()
    call_args = mock_client.request.call_args
    assert call_args[0][0] == "POST"
    assert call_args[1]["headers"] == {"Content-Type": "application/json"}
    assert call_args[1]["content"] == '{"key": "value"}'


@patch("checks.httpx.Client")
def test_check_custom_header(mock_client_class):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    create_resp = client.post(
        "/endpoints",
        json={
            "name": "Header API",
            "url": "https://example.com/api",
            "method": "GET",
            "request_headers": {"Authorization": "Bearer token123"},
        },
    )
    assert create_resp.status_code == 201
    endpoint = create_resp.json()

    response = client.post(f"/endpoints/{endpoint['id']}/checks")
    assert response.status_code == 201

    mock_client.request.assert_called_once()
    call_args = mock_client.request.call_args
    assert call_args[0][0] == "GET"
    assert call_args[1]["headers"] == {"Authorization": "Bearer token123"}
    assert call_args[1]["content"] is None


@patch("checks.httpx.Client")
def test_check_head_method(mock_client_class):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client = MagicMock()
    mock_client.request.return_value = mock_response
    mock_client_class.return_value.__enter__.return_value = mock_client

    create_resp = client.post(
        "/endpoints",
        json={
            "name": "HEAD API",
            "url": "https://example.com/api",
            "method": "HEAD",
        },
    )
    assert create_resp.status_code == 201
    endpoint = create_resp.json()
    assert endpoint["method"] == "HEAD"

    response = client.post(f"/endpoints/{endpoint['id']}/checks")
    assert response.status_code == 201

    mock_client.request.assert_called_once()
    call_args = mock_client.request.call_args
    assert call_args[0][0] == "HEAD"
def test_list_checks_filter_success_true():
    endpoint = _create_endpoint()

    with patch("checks._execute_http_request", return_value=MagicMock(status_code=200)):
        for _ in range(2):
            resp = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert resp.status_code == 201

    with patch("checks._execute_http_request", return_value=MagicMock(status_code=500)):
        for _ in range(2):
            resp = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert resp.status_code == 201

    response = client.get(f"/endpoints/{endpoint['id']}/checks?success=true")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["meta"]["total"] == 2
    for item in body["items"]:
        assert item["success"] is True


def test_list_checks_filter_success_false():
    endpoint = _create_endpoint()

    with patch("checks._execute_http_request", return_value=MagicMock(status_code=200)):
        for _ in range(2):
            resp = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert resp.status_code == 201

    with patch("checks._execute_http_request", return_value=MagicMock(status_code=500)):
        for _ in range(2):
            resp = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert resp.status_code == 201

    response = client.get(f"/endpoints/{endpoint['id']}/checks?success=false")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["meta"]["total"] == 2
    for item in body["items"]:
        assert item["success"] is False


def test_list_checks_filter_since(db_session):
    endpoint = _create_endpoint()
    base = datetime(2026, 1, 1, 12, 0, 0)

    for i in range(3):
        db_session.add(
            Check(
                endpoint_id=endpoint["id"],
                url="https://example.com/api",
                expected_status_code=200,
                actual_status_code=200,
                response_time_ms=10,
                success=True,
                checked_at=base.replace(minute=i),
            )
        )
    db_session.commit()

    since = base.replace(minute=1).isoformat()
    response = client.get(
        f"/endpoints/{endpoint['id']}/checks",
        params={"since": since},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["meta"]["total"] == 2
    for item in body["items"]:
        assert item["checked_at"] >= since


def test_list_checks_filter_until(db_session):
    endpoint = _create_endpoint()
    base = datetime(2026, 1, 1, 12, 0, 0)

    for i in range(3):
        db_session.add(
            Check(
                endpoint_id=endpoint["id"],
                url="https://example.com/api",
                expected_status_code=200,
                actual_status_code=200,
                response_time_ms=10,
                success=True,
                checked_at=base.replace(minute=i),
            )
        )
    db_session.commit()

    until = base.replace(minute=1).isoformat()
    response = client.get(
        f"/endpoints/{endpoint['id']}/checks",
        params={"until": until},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["meta"]["total"] == 2
    for item in body["items"]:
        assert item["checked_at"] <= until


def test_list_checks_filter_combined(db_session):
    endpoint = _create_endpoint()
    base = datetime(2026, 1, 1, 12, 0, 0)

    checks_data = [
        (True, 0),
        (False, 1),
        (True, 2),
        (False, 3),
    ]
    for success, minute in checks_data:
        db_session.add(
            Check(
                endpoint_id=endpoint["id"],
                url="https://example.com/api",
                expected_status_code=200,
                actual_status_code=200 if success else 500,
                response_time_ms=10,
                success=success,
                checked_at=base.replace(minute=minute),
            )
        )
    db_session.commit()

    response = client.get(
        f"/endpoints/{endpoint['id']}/checks",
        params={
            "since": base.replace(minute=1).isoformat(),
            "until": base.replace(minute=2).isoformat(),
            "success": "true",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["meta"]["total"] == 1
    assert body["items"][0]["success"] is True
    assert body["items"][0]["checked_at"] == base.replace(minute=2).isoformat()


def test_list_checks_filter_with_pagination(db_session):
    endpoint = _create_endpoint()
    base = datetime(2026, 1, 1, 12, 0, 0)

    for i in range(4):
        db_session.add(
            Check(
                endpoint_id=endpoint["id"],
                url="https://example.com/api",
                expected_status_code=200,
                actual_status_code=200,
                response_time_ms=10,
                success=True,
                checked_at=base.replace(minute=i),
            )
        )
    db_session.commit()

    since = base.isoformat()
    response = client.get(
        f"/endpoints/{endpoint['id']}/checks",
        params={"since": since, "limit": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["meta"]["total"] == 4
    assert body["meta"]["limit"] == 2
