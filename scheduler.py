import asyncio
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from checks import run_endpoint_check
from database import SessionLocal
from models import Check, Endpoint

log = logging.getLogger("probepilot.scheduler")

SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "false").lower() in ("true", "1", "yes")
SCHEDULER_INTERVAL_SECONDS = int(os.environ.get("SCHEDULER_INTERVAL_SECONDS", "60"))

_task: asyncio.Task | None = None
_stop_event: asyncio.Event = asyncio.Event()
_paused: bool = False
_last_run_at: datetime | None = None

# Overridable seam for tests
_session_factory = SessionLocal


def _tick(db: Session, now: datetime) -> int:
    """Run one scheduler tick. Returns number of checks performed."""
    count = 0
    endpoints = (
        db.query(Endpoint)
        .filter(Endpoint.check_interval_seconds.isnot(None), Endpoint.enabled.is_(True))
        .all()
    )
    for endpoint in endpoints:
        last_check = (
            db.query(Check)
            .filter(Check.endpoint_id == endpoint.id)
            .order_by(desc(Check.checked_at))
            .first()
        )
        if last_check is None:
            run_endpoint_check(db, endpoint)
            count += 1
        else:
            checked_at = last_check.checked_at
            if checked_at is not None and checked_at.tzinfo is None:
                checked_at = checked_at.replace(tzinfo=timezone.utc)
            elapsed = (now - checked_at).total_seconds()
            interval = endpoint.check_interval_seconds
            assert interval is not None
            if elapsed >= interval:
                run_endpoint_check(db, endpoint)
                count += 1
    return count


async def _loop() -> None:
    global _last_run_at
    while not _stop_event.is_set():
        if not _paused:
            try:
                db = _session_factory()
                try:
                    now = datetime.now(timezone.utc)
                    count = _tick(db, now)
                    _last_run_at = now
                    if count:
                        log.info("scheduler_tick", extra={"checks_run": count})
                finally:
                    db.close()
            except Exception:
                log.exception("scheduler_tick_error")

        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=SCHEDULER_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass


def start_scheduler() -> None:
    global _task
    if not SCHEDULER_ENABLED:
        log.info("scheduler_disabled_by_config")
        return
    if _task is not None:
        return
    _stop_event.clear()
    _task = asyncio.create_task(_loop())
    log.info("scheduler_started", extra={"interval_seconds": SCHEDULER_INTERVAL_SECONDS})


def stop_scheduler() -> None:
    global _task
    if _task is None:
        return
    _stop_event.set()
    _task.cancel()
    log.info("scheduler_stopped")
    _task = None


def pause_scheduler() -> None:
    global _paused
    _paused = True
    log.info("scheduler_paused")


def resume_scheduler() -> None:
    global _paused
    _paused = False
    log.info("scheduler_resumed")


def is_scheduler_paused() -> bool:
    return _paused


def get_scheduler_status(db: Session | None = None) -> dict:
    close_db = False
    if db is None:
        db = _session_factory()
        close_db = True
    try:
        endpoints_scheduled = (
            db.query(Endpoint)
            .filter(Endpoint.check_interval_seconds.isnot(None))
            .count()
        )
    finally:
        if close_db:
            db.close()
    return {
        "enabled": SCHEDULER_ENABLED and _task is not None,
        "interval_seconds": SCHEDULER_INTERVAL_SECONDS,
        "endpoints_scheduled": endpoints_scheduled,
        "last_run_at": _last_run_at.isoformat() if _last_run_at else None,
        "paused": _paused,
    }
