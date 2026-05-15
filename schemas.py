from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

HttpMethod = Literal["GET", "POST", "HEAD", "PUT", "DELETE", "PATCH"]


class EndpointCreate(BaseModel):
    name: str = Field(..., min_length=1)
    url: HttpUrl
    expected_status_code: int = Field(default=200)
    timeout_seconds: float = Field(default=5.0, gt=0)
    method: HttpMethod = Field(default="GET")
    request_headers: dict[str, str] | None = Field(default=None)
    request_body: str | None = Field(default=None)
    enabled: bool = Field(default=True)


class EndpointUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    url: HttpUrl | None = Field(default=None)
    expected_status_code: int | None = Field(default=None)
    timeout_seconds: float | None = Field(default=None, gt=0)
    method: HttpMethod | None = Field(default=None)
    request_headers: dict[str, str] | None = Field(default=None)
    request_body: str | None = Field(default=None)
    enabled: bool | None = Field(default=None)


class EndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    expected_status_code: int
    timeout_seconds: float
    method: str
    request_headers: dict | None
    request_body: str | None
    enabled: bool
    created_at: datetime


class CheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    endpoint_id: int
    url: str
    expected_status_code: int
    actual_status_code: int | None
    response_time_ms: int | None
    success: bool
    error_message: str | None
    checked_at: datetime


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    endpoint_id: int
    title: str
    status: str
    failure_count: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int


class EndpointsPage(BaseModel):
    items: list[EndpointResponse]
    meta: PageMeta


class ChecksPage(BaseModel):
    items: list[CheckResponse]
    meta: PageMeta


class IncidentsPage(BaseModel):
    items: list[IncidentResponse]
    meta: PageMeta


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    version: str
    db: Literal["ok", "error"]
    error: str | None
