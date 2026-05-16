import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import tomllib

from alembic import command
from alembic.config import Config
from fastapi import Depends, FastAPI, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from checks import router as checks_router
from database import get_db
from endpoints import router as endpoints_router
from incidents import router as incidents_router
from logging_config import setup_logging
from metrics import router as metrics_router
from schemas import HealthResponse
from scheduler import start_scheduler, stop_scheduler
from scheduler_api import router as scheduler_router

setup_logging()

_APP_VERSION: str = "unknown"
try:
    _pyproject_path = Path(__file__).parent / "pyproject.toml"
    with _pyproject_path.open("rb") as f:
        _APP_VERSION = tomllib.load(f)["project"]["version"]
except Exception:
    _APP_VERSION = "unknown"


@asynccontextmanager
async def lifespan(app: FastAPI):
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="ProbePilot", lifespan=lifespan)
app.include_router(endpoints_router)
app.include_router(checks_router)
app.include_router(incidents_router)
app.include_router(scheduler_router)


@app.get("/health", response_model=HealthResponse)
def health_check(db=Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return HealthResponse(
            status="healthy",
            version=_APP_VERSION,
            db="ok",
            error=None,
        )
    except SQLAlchemyError as exc:
        return HealthResponse(
            status="degraded",
            version=_APP_VERSION,
            db="error",
            error=str(exc)[:200],
        )
