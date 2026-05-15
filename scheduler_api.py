from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from scheduler import (
    get_scheduler_status,
    pause_scheduler,
    resume_scheduler,
)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/status")
def scheduler_status(db: Session = Depends(get_db)):
    return get_scheduler_status(db)


@router.post("/pause")
def scheduler_pause(db: Session = Depends(get_db)):
    pause_scheduler()
    return get_scheduler_status(db)


@router.post("/resume")
def scheduler_resume(db: Session = Depends(get_db)):
    resume_scheduler()
    return get_scheduler_status(db)
