from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from models import Endpoint
from schemas import EndpointCreate, EndpointResponse, EndpointUpdate, EndpointsPage, PageMeta

router = APIRouter(prefix="/endpoints", tags=["endpoints"])


@router.post("", response_model=EndpointResponse, status_code=status.HTTP_201_CREATED)
def create_endpoint(data: EndpointCreate, db: Session = Depends(get_db)):
    endpoint = Endpoint(
        name=data.name,
        url=str(data.url),
        expected_status_code=data.expected_status_code,
        timeout_seconds=data.timeout_seconds,
        method=data.method,
        request_headers=data.request_headers,
        request_body=data.request_body,
        enabled=data.enabled,
        check_interval_seconds=data.check_interval_seconds,
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint


@router.get("", response_model=EndpointsPage)
def list_endpoints(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, min_length=1),
):
    query = db.query(Endpoint)
    if q:
        query = query.filter(
            or_(
                Endpoint.name.ilike(f"%{q}%"),
                Endpoint.url.ilike(f"%{q}%"),
            )
        )
    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    return EndpointsPage(
        items=[EndpointResponse.model_validate(r) for r in rows],
        meta=PageMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/{endpoint_id}", response_model=EndpointResponse)
def get_endpoint(endpoint_id: int, db: Session = Depends(get_db)):
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")
    return endpoint


def _update_endpoint(endpoint: Endpoint, data: EndpointUpdate) -> None:
    if data.name is not None:
        endpoint.name = data.name
    if data.url is not None:
        endpoint.url = str(data.url)
    if data.expected_status_code is not None:
        endpoint.expected_status_code = data.expected_status_code
    if data.timeout_seconds is not None:
        endpoint.timeout_seconds = data.timeout_seconds
    if data.method is not None:
        endpoint.method = data.method
    if data.request_headers is not None:
        endpoint.request_headers = data.request_headers
    if data.request_body is not None:
        endpoint.request_body = data.request_body
    if data.enabled is not None:
        endpoint.enabled = data.enabled
    if data.check_interval_seconds is not None:
        endpoint.check_interval_seconds = data.check_interval_seconds


@router.put("/{endpoint_id}", response_model=EndpointResponse)
def update_endpoint(endpoint_id: int, data: EndpointUpdate, db: Session = Depends(get_db)):
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")

    _update_endpoint(endpoint, data)

    db.commit()
    db.refresh(endpoint)
    return endpoint


@router.patch("/{endpoint_id}", response_model=EndpointResponse)
def patch_endpoint(endpoint_id: int, data: EndpointUpdate, db: Session = Depends(get_db)):
    endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")

    _update_endpoint(endpoint, data)

    db.commit()
    db.refresh(endpoint)
    return endpoint
