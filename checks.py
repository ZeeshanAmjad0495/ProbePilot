import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import Check, Endpoint, Incident
from schemas import CheckResponse

router = APIRouter(prefix="/endpoints", tags=["checks"])


def _evaluate_incidents(db: Session, endpoint_id: int, success: bool) -> None:
    if success:
        open_incident = (
            db.query(Incident)
            .filter(Incident.endpoint_id == endpoint_id, Incident.status == "open")
            .first()
        )
        if open_incident:
            open_incident.status = "resolved"
            open_incident.resolved_at = datetime.now(timezone.utc)
        return

    recent_checks = (
        db.query(Check)
        .filter(Check.endpoint_id == endpoint_id)
        .order_by(desc(Check.checked_at))
        .limit(3)
        .all()
    )

    if len(recent_checks) < 3 or any(check.success for check in recent_checks):
        return

    open_incident = (
        db.query(Incident)
        .filter(Incident.endpoint_id == endpoint_id, Incident.status == "open")
        .first()
    )

    if open_incident:
        open_incident.failure_count += 1
        open_incident.updated_at = datetime.now(timezone.utc)
    else:
        incident = Incident(
            endpoint_id=endpoint_id,
            title="Endpoint failure detected",
            status="open",
            failure_count=3,
        )
        db.add(incident)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            open_incident = (
                db.query(Incident)
                .filter(Incident.endpoint_id == endpoint_id, Incident.status == "open")
                .first()
            )
            if open_incident:
                open_incident.failure_count += 1
                open_incident.updated_at = datetime.now(timezone.utc)


@router.post("/{endpoint_id}/checks", response_model=CheckResponse, status_code=status.HTTP_201_CREATED)
def trigger_check(endpoint_id: int, db: Session = Depends(get_db)):
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")

    start = time.perf_counter()
    try:
        with httpx.Client(timeout=endpoint.timeout_seconds) as client:
            response = client.get(endpoint.url)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        actual_status_code = response.status_code
        success = actual_status_code == endpoint.expected_status_code
        error_message = None
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError) as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        actual_status_code = None
        success = False
        error_message = str(exc)

    check = Check(
        endpoint_id=endpoint.id,
        url=endpoint.url,
        expected_status_code=endpoint.expected_status_code,
        actual_status_code=actual_status_code,
        response_time_ms=elapsed_ms,
        success=success,
        error_message=error_message,
    )
    db.add(check)
    db.commit()
    db.refresh(check)

    _evaluate_incidents(db, endpoint.id, success)
    db.commit()

    return check


@router.get("/{endpoint_id}/checks", response_model=list[CheckResponse])
def list_checks(endpoint_id: int, db: Session = Depends(get_db)):
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")

    checks = (
        db.query(Check)
        .filter(Check.endpoint_id == endpoint_id)
        .order_by(desc(Check.checked_at))
        .all()
    )
    return checks
