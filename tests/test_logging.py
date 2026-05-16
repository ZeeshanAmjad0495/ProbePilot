import json
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


def _find_record(records, message):
    for record in records:
        if record.message == message:
            return record
    return None


def test_log_check_executed_failure(caplog):
    endpoint = _create_endpoint()

    with patch("checks._execute_http_request", return_value=_mock_failure()):
        response = client.post(f"/endpoints/{endpoint['id']}/checks")
        assert response.status_code == 201

    record = _find_record(caplog.records, "check_executed")
    assert record is not None
    assert record.endpoint_id == endpoint["id"]
    assert record.success is False
    assert isinstance(record.response_time_ms, int)


def test_log_incident_opened_after_three_failures(caplog):
    endpoint = _create_endpoint()

    with patch("checks._execute_http_request", return_value=_mock_failure()):
        for _ in range(3):
            response = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert response.status_code == 201

    record = _find_record(caplog.records, "incident_opened")
    assert record is not None
    assert record.endpoint_id == endpoint["id"]
    assert record.failure_count == 3


def test_log_incident_resolved_manual(caplog):
    endpoint = _create_endpoint()

    with patch("checks._execute_http_request", return_value=_mock_failure()):
        for _ in range(3):
            response = client.post(f"/endpoints/{endpoint['id']}/checks")
            assert response.status_code == 201

    incidents_response = client.get(f"/endpoints/{endpoint['id']}/incidents")
    incident_id = incidents_response.json()["items"][0]["id"]

    with caplog.at_level("INFO", logger="probepilot.incidents"):
        response = client.post(f"/incidents/{incident_id}/resolve")
        assert response.status_code == 200

    record = _find_record(caplog.records, "incident_resolved_manual")
    assert record is not None
    assert record.incident_id == incident_id
    assert record.endpoint_id == endpoint["id"]


def test_resolve_incident_not_found():
    response = client.post("/incidents/999/resolve")
    assert response.status_code == 404
    assert response.json()["detail"] == "Incident not found"


def test_setup_logging_idempotent():
    import logging

    from logging_config import setup_logging

    setup_logging()
    root = logging.getLogger()
    handler_count = len(root.handlers)
    setup_logging()
    assert len(root.handlers) == handler_count


def test_json_formatter_outputs_valid_json():
    import logging

    from logging_config import JsonFormatter

    formatter = JsonFormatter()
    test_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="test_event",
        args=(),
        exc_info=None,
    )
    test_record.key = "value"
    output = formatter.format(test_record)
    parsed = json.loads(output)
    assert parsed["message"] == "test_event"
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test"
    assert parsed["key"] == "value"
    assert "ts" in parsed
    assert parsed["ts"].endswith("+00:00")


def test_middleware_logs_request(caplog):
    with caplog.at_level("INFO", logger="probepilot.middleware"):
        response = client.get("/health")
        assert response.status_code == 200

    record = _find_record(caplog.records, "request_completed")
    assert record is not None
    assert record.method == "GET"
    assert record.path == "/health"
    assert record.status_code == 200
    assert isinstance(record.duration_ms, int)


def test_middleware_json_format():
    import logging

    from logging_config import JsonFormatter

    formatter = JsonFormatter()
    test_record = logging.LogRecord(
        name="probepilot.middleware",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="request_completed",
        args=(),
        exc_info=None,
    )
    test_record.method = "GET"
    test_record.path = "/health"
    test_record.status_code = 200
    test_record.duration_ms = 42
    output = formatter.format(test_record)
    parsed = json.loads(output)
    assert parsed["message"] == "request_completed"
    assert parsed["method"] == "GET"
    assert parsed["path"] == "/health"
    assert parsed["status_code"] == 200
    assert parsed["duration_ms"] == 42
    assert parsed["ts"].endswith("+00:00")
