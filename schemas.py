from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class EndpointCreate(BaseModel):
    name: str = Field(..., min_length=1)
    url: HttpUrl
    expected_status_code: int = Field(default=200)
    timeout_seconds: float = Field(default=5.0, gt=0)


class EndpointUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    url: HttpUrl | None = Field(default=None)
    expected_status_code: int | None = Field(default=None)
    timeout_seconds: float | None = Field(default=None, gt=0)


class EndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    expected_status_code: int
    timeout_seconds: float
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
