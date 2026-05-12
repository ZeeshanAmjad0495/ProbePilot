from fastapi import FastAPI

from database import engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ProbePilot")


@app.get("/health")
def health_check():
    return {"status": "healthy"}
