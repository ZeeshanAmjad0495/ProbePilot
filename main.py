from contextlib import asynccontextmanager

from fastapi import FastAPI

import database
from endpoints import router as endpoints_router
from checks import router as checks_router
from incidents import router as incidents_router
from logging_config import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.Base.metadata.create_all(bind=database.engine)
    yield


app = FastAPI(title="ProbePilot", lifespan=lifespan)
app.include_router(endpoints_router)
app.include_router(checks_router)
app.include_router(incidents_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
