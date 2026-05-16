from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from models import Check, Endpoint
from scheduler import (
    _tick,
    get_scheduler_status,
    is_scheduler_paused,
    pause_scheduler,
    resume_scheduler,
    start_scheduler,
    stop_scheduler,
)


class TestTick:
    def test_tick_runs_check_when_no_prior_check(self, db_session):
        endpoint = Endpoint(
            name="Test",
            url="https://example.com",
            check_interval_seconds=60,
            enabled=True,
        )
        db_session.add(endpoint)
        db_session.commit()

        with patch("checks.httpx.Client") as mock_class:
            mock_class.return_value.__enter__.return_value.request.return_value = MagicMock(
                status_code=200
            )
            count = _tick(db_session, datetime.now(timezone.utc))

        assert count == 1
        assert db_session.query(Check).filter(Check.endpoint_id == endpoint.id).count() == 1

    def test_tick_skips_when_interval_not_elapsed(self, db_session):
        endpoint = Endpoint(
            name="Test",
            url="https://example.com",
            check_interval_seconds=60,
            enabled=True,
        )
        db_session.add(endpoint)
        db_session.commit()

        # Create a recent check
        check = Check(
            endpoint_id=endpoint.id,
            url=endpoint.url,
            expected_status_code=200,
            actual_status_code=200,
            response_time_ms=10,
            success=True,
            checked_at=datetime.now(timezone.utc) - timedelta(seconds=30),
        )
        db_session.add(check)
        db_session.commit()

        with patch("checks.httpx.Client") as mock_class:
            mock_class.return_value.__enter__.return_value.request.return_value = MagicMock(
                status_code=200
            )
            count = _tick(db_session, datetime.now(timezone.utc))

        assert count == 0
        assert db_session.query(Check).filter(Check.endpoint_id == endpoint.id).count() == 1

    def test_tick_runs_when_interval_elapsed(self, db_session):
        endpoint = Endpoint(
            name="Test",
            url="https://example.com",
            check_interval_seconds=60,
            enabled=True,
        )
        db_session.add(endpoint)
        db_session.commit()

        # Create an old check
        check = Check(
            endpoint_id=endpoint.id,
            url=endpoint.url,
            expected_status_code=200,
            actual_status_code=200,
            response_time_ms=10,
            success=True,
            checked_at=datetime.now(timezone.utc) - timedelta(seconds=120),
        )
        db_session.add(check)
        db_session.commit()

        with patch("checks.httpx.Client") as mock_class:
            mock_class.return_value.__enter__.return_value.request.return_value = MagicMock(
                status_code=200
            )
            count = _tick(db_session, datetime.now(timezone.utc))

        assert count == 1
        assert db_session.query(Check).filter(Check.endpoint_id == endpoint.id).count() == 2

    def test_tick_skips_disabled_endpoints(self, db_session):
        endpoint = Endpoint(
            name="Test",
            url="https://example.com",
            check_interval_seconds=60,
            enabled=False,
        )
        db_session.add(endpoint)
        db_session.commit()

        with patch("checks.httpx.Client") as mock_class:
            mock_class.return_value.__enter__.return_value.request.return_value = MagicMock(
                status_code=200
            )
            count = _tick(db_session, datetime.now(timezone.utc))

        assert count == 0
        assert db_session.query(Check).filter(Check.endpoint_id == endpoint.id).count() == 0

    def test_tick_skips_endpoints_without_interval(self, db_session):
        endpoint = Endpoint(
            name="Test",
            url="https://example.com",
            check_interval_seconds=None,
            enabled=True,
        )
        db_session.add(endpoint)
        db_session.commit()

        with patch("checks.httpx.Client") as mock_class:
            mock_class.return_value.__enter__.return_value.request.return_value = MagicMock(
                status_code=200
            )
            count = _tick(db_session, datetime.now(timezone.utc))

        assert count == 0
        assert db_session.query(Check).filter(Check.endpoint_id == endpoint.id).count() == 0

    def test_tick_handles_empty_endpoints(self, db_session):
        with patch("checks.httpx.Client") as mock_class:
            mock_class.return_value.__enter__.return_value.request.return_value = MagicMock(
                status_code=200
            )
            count = _tick(db_session, datetime.now(timezone.utc))

        assert count == 0

    def test_tick_runs_multiple_due_endpoints(self, db_session):
        e1 = Endpoint(name="A", url="https://a.com", check_interval_seconds=60, enabled=True)
        e2 = Endpoint(name="B", url="https://b.com", check_interval_seconds=60, enabled=True)
        db_session.add_all([e1, e2])
        db_session.commit()

        with patch("checks.httpx.Client") as mock_class:
            mock_class.return_value.__enter__.return_value.request.return_value = MagicMock(
                status_code=200
            )
            count = _tick(db_session, datetime.now(timezone.utc))

        assert count == 2
        assert db_session.query(Check).count() == 2

    def test_tick_evaluates_incidents_on_failure(self, db_session):
        endpoint = Endpoint(
            name="Test",
            url="https://example.com",
            check_interval_seconds=60,
            enabled=True,
        )
        db_session.add(endpoint)
        db_session.commit()

        with patch("checks.httpx.Client") as mock_class:
            mock_class.return_value.__enter__.return_value.request.return_value = MagicMock(
                status_code=500
            )
            count = _tick(db_session, datetime.now(timezone.utc))

        assert count == 1
        check = db_session.query(Check).first()
        assert check.success is False


class TestSchedulerLifecycle:
    @patch("scheduler.SCHEDULER_ENABLED", True)
    @patch("scheduler.SCHEDULER_INTERVAL_SECONDS", 0.001)
    @patch("scheduler._session_factory")
    def test_start_stop_lifecycle(self, mock_session_factory):
        import asyncio

        async def _test():
            start_scheduler()
            await asyncio.sleep(0.05)
            stop_scheduler()

        asyncio.run(_test())

    def test_start_scheduler_disabled(self):
        with patch("scheduler.SCHEDULER_ENABLED", False):
            start_scheduler()
            # Should be a no-op
            stop_scheduler()


class TestSchedulerStatus:
    def test_pause_resume(self):
        assert is_scheduler_paused() is False
        pause_scheduler()
        assert is_scheduler_paused() is True
        resume_scheduler()
        assert is_scheduler_paused() is False

    def test_get_scheduler_status(self, db_session):
        with patch("scheduler._session_factory", return_value=db_session):
            status = get_scheduler_status()
            assert "enabled" in status
            assert "interval_seconds" in status
            assert "endpoints_scheduled" in status
            assert "last_run_at" in status
            assert "paused" in status
