from sqlalchemy import Column, Integer, String, Float, DateTime, func

from database import Base


class Endpoint(Base):
    __tablename__ = "endpoints"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    expected_status_code = Column(Integer, default=200)
    timeout_seconds = Column(Float, default=5.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
