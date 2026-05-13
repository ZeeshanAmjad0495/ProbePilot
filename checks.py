import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from database import get_db
from models import Check, Endpoint
from schemas import CheckResponse

router = APIRouter(prefix="/endpoints", tags=["checks"])


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
