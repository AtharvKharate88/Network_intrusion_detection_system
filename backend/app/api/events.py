from fastapi import APIRouter, Depends, HTTPException
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
    db_event = NetworkEvent(**event.model_dump())

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
    limit: int = 50,
    db: Session = Depends(get_db),
):
    if not 1 <= limit <= 100:
        raise HTTPException(
            status_code=422,
            detail="limit must be between 1 and 100",
        )

    statement = (
        select(NetworkEvent)
        .order_by(NetworkEvent.created_at.desc())
        .limit(limit)
    )

    return db.scalars(statement).all()