from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_db
from models import Check, Endpoint, Incident
from schemas import MetricsSummary

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_model=MetricsSummary)
def get_metrics(db: Session = Depends(get_db)):
    total_endpoints = db.query(Endpoint).count()

    latest_check_subq = (
        select(Check.endpoint_id, func.max(Check.id).label("max_id"))
        .group_by(Check.endpoint_id)
        .subquery()
    )

    latest_checks = (
        db.query(Check)
        .join(latest_check_subq, Check.id == latest_check_subq.c.max_id)
        .all()
    )

    endpoints_up = sum(1 for check in latest_checks if check.success)
    endpoints_down = sum(1 for check in latest_checks if not check.success)

    open_incidents = db.query(Incident).filter(Incident.status == "open").count()
    resolved_incidents = (
        db.query(Incident).filter(Incident.status == "resolved").count()
    )

    return MetricsSummary(
        total_endpoints=total_endpoints,
        endpoints_up=endpoints_up,
        endpoints_down=endpoints_down,
        open_incidents=open_incidents,
        resolved_incidents=resolved_incidents,
    )
