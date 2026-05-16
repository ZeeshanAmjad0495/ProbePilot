from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_scheduler_status():
    response = client.get("/scheduler/status")
    assert response.status_code == 200
    body = response.json()
    assert "enabled" in body
    assert "interval_seconds" in body
    assert "endpoints_scheduled" in body
    assert "last_run_at" in body
    assert "paused" in body


def test_scheduler_pause_resume():
    with patch("scheduler_api.pause_scheduler") as mock_pause:
        response = client.post("/scheduler/pause")
        assert response.status_code == 200
        mock_pause.assert_called_once()

    with patch("scheduler_api.resume_scheduler") as mock_resume:
        response = client.post("/scheduler/resume")
        assert response.status_code == 200
        mock_resume.assert_called_once()
