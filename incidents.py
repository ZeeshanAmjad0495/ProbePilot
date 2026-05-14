import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from database import get_db
from models import Endpoint, Incident
from schemas import IncidentResponse, IncidentsPage, PageMeta

router = APIRouter(tags=["incidents"])
log = logging.getLogger("probepilot.incidents")


@router.get("/endpoints/{endpoint_id}/incidents", response_model=IncidentsPage)
def list_incidents(
    endpoint_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")

    total = db.query(Incident).filter(Incident.endpoint_id == endpoint_id).count()
    incidents = (
        db.query(Incident)
        .filter(Incident.endpoint_id == endpoint_id)
        .order_by(desc(Incident.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return IncidentsPage(
        items=[IncidentResponse.model_validate(i) for i in incidents],
        meta=PageMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident


@router.post("/incidents/{incident_id}/resolve", response_model=IncidentResponse)
def resolve_incident(incident_id: int, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    incident.status = "resolved"
    incident.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(incident)

    log.info(
        "incident_resolved_manual",
        extra={"incident_id": incident.id, "endpoint_id": incident.endpoint_id},
    )

    return incident
