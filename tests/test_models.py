from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import Endpoint, Check, Incident


def test_check_and_incident_models():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    endpoint = Endpoint(
        name="Test API",
        url="https://example.com/api",
        expected_status_code=200,
        timeout_seconds=3.0,
    )
    session.add(endpoint)
    session.commit()
    session.refresh(endpoint)

    check = Check(
        endpoint_id=endpoint.id,
        url=endpoint.url,
        expected_status_code=endpoint.expected_status_code,
        actual_status_code=200,
        response_time_ms=150,
        success=True,
        error_message=None,
    )
    session.add(check)
    session.commit()
    session.refresh(check)

    incident = Incident(
        endpoint_id=endpoint.id,
        title="Test API down",
        status="open",
        failure_count=3,
    )
    session.add(incident)
    session.commit()
    session.refresh(incident)

    retrieved_check = session.query(Check).filter_by(id=check.id).first()
    assert retrieved_check is not None
    assert retrieved_check.endpoint_id == endpoint.id
    assert retrieved_check.url == "https://example.com/api"
    assert retrieved_check.expected_status_code == 200
    assert retrieved_check.actual_status_code == 200
    assert retrieved_check.response_time_ms == 150
    assert retrieved_check.success is True
    assert retrieved_check.error_message is None
    assert retrieved_check.checked_at is not None

    retrieved_incident = session.query(Incident).filter_by(id=incident.id).first()
    assert retrieved_incident is not None
    assert retrieved_incident.endpoint_id == endpoint.id
    assert retrieved_incident.title == "Test API down"
    assert retrieved_incident.status == "open"
    assert retrieved_incident.failure_count == 3
    assert retrieved_incident.created_at is not None
    assert retrieved_incident.resolved_at is None

    session.close()
