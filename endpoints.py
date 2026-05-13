from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import Endpoint
from schemas import EndpointCreate, EndpointResponse, EndpointUpdate

router = APIRouter(prefix="/endpoints", tags=["endpoints"])


@router.post("", response_model=EndpointResponse, status_code=status.HTTP_201_CREATED)
def create_endpoint(data: EndpointCreate, db: Session = Depends(get_db)):
    endpoint = Endpoint(
        name=data.name,
        url=str(data.url),
        expected_status_code=data.expected_status_code,
        timeout_seconds=data.timeout_seconds,
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint


@router.get("", response_model=list[EndpointResponse])
def list_endpoints(db: Session = Depends(get_db)):
    return db.query(Endpoint).all()


@router.get("/{endpoint_id}", response_model=EndpointResponse)
def get_endpoint(endpoint_id: int, db: Session = Depends(get_db)):
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")
    return endpoint


@router.put("/{endpoint_id}", response_model=EndpointResponse)
def update_endpoint(endpoint_id: int, data: EndpointUpdate, db: Session = Depends(get_db)):
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")

    if data.name is not None:
        endpoint.name = data.name
    if data.url is not None:
        endpoint.url = str(data.url)
    if data.expected_status_code is not None:
        endpoint.expected_status_code = data.expected_status_code
    if data.timeout_seconds is not None:
        endpoint.timeout_seconds = data.timeout_seconds

    db.commit()
    db.refresh(endpoint)
    return endpoint
