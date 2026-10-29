from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import NetworkEvent
from app.schemas.event import EventCreate, EventResponse

router = APIRouter(prefix="/api/events", tags=["Events"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=EventResponse, status_code=201)
def create_event(
    event: EventCreate,
    db: Session = Depends(get_db),
):
    event_data = event.model_dump()
    for field in ("source_ip", "destination_ip"):
        if event_data[field] is not None:
            event_data[field] = str(event_data[field])
    db_event = NetworkEvent(**event_data)

    db.add(db_event)

    try:
        db.commit()
        db.refresh(db_event)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An event with this flow_id already exists.",
        )

    return db_event


@router.get("", response_model=list[EventResponse])
def list_events(
    limit: int = Query(default=50, ge=1, le=100),
    predicted_class: str | None = Query(default=None, min_length=1),
    alert: bool | None = None,
    source_ip: str | None = Query(default=None, min_length=1),
    destination_ip: str | None = Query(default=None, min_length=1),
    db: Session = Depends(get_db),
):
    statement = (
        select(NetworkEvent)
        .order_by(NetworkEvent.created_at.desc())
        .limit(limit)
    )
    if predicted_class:
        statement = statement.where(
            NetworkEvent.predicted_class == predicted_class
        )
    if alert is not None:
        statement = statement.where(NetworkEvent.alert == alert)
    if source_ip:
        statement = statement.where(NetworkEvent.source_ip == source_ip)
    if destination_ip:
        statement = statement.where(NetworkEvent.destination_ip == destination_ip)

    return db.scalars(statement).all()


@router.get("/stats")
def event_stats(db: Session = Depends(get_db)):
    """Return dashboard aggregates from persisted events."""

    events = db.scalars(select(NetworkEvent)).all()
    distribution: dict[str, int] = {}
    for event in events:
        distribution[event.predicted_class] = (
            distribution.get(event.predicted_class, 0) + 1
        )

    return {
        "total_events": len(events),
        "total_alerts": sum(event.alert for event in events),
        "attack_events": sum(event.predicted_class != "Normal" for event in events),
        "normal_events": sum(event.predicted_class == "Normal" for event in events),
        "attack_distribution": distribution,
    }