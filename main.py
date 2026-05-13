from fastapi import FastAPI

from database import engine, Base
from endpoints import router as endpoints_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ProbePilot")
app.include_router(endpoints_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
