from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from database import get_db
from models import Endpoint, Incident
from schemas import IncidentResponse

router = APIRouter(tags=["incidents"])


@router.get("/endpoints/{endpoint_id}/incidents", response_model=list[IncidentResponse])
def list_incidents(endpoint_id: int, db: Session = Depends(get_db)):
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")

    incidents = (
        db.query(Incident)
        .filter(Incident.endpoint_id == endpoint_id)
        .order_by(desc(Incident.created_at))
        .all()
    )
    return incidents


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident
