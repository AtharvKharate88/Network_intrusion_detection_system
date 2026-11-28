from fastapi import (
    APIRouter, Depends, HTTPException, Query
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.events import get_db
from app.db.models import BehavioralAlert
from app.schemas.behavioral import (
    BehavioralAlertCreate,
    BehavioralAlertResponse
)

router = APIRouter(
    prefix="/api/behavioral-alerts",
    tags=["Behavioral Detection"]
)


@router.post(
    "",
    response_model=BehavioralAlertResponse,
    status_code=201
)
def create_alert(
    alert: BehavioralAlertCreate,
    db: Session = Depends(get_db)
):
    data = alert.model_dump()

    data["source_ip"] = str(data["source_ip"])
    data["destination_ip"] = str(data["destination_ip"])

    record = BehavioralAlert(**data)
    db.add(record)

    try:
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Behavioral alert already exists."
        )

    return record


@router.get(
    "",
    response_model=list[BehavioralAlertResponse]
)
def list_alerts(
    limit: int = Query(default=50, ge=1, le=100),
    session_id: str | None = None,
    db: Session = Depends(get_db)
):
    statement = select(BehavioralAlert)

    if session_id:
        statement = statement.where(
            BehavioralAlert.session_id == session_id
        )

    statement = statement.order_by(
        BehavioralAlert.observed_at.desc()
    ).limit(limit)

    return db.scalars(statement).all()
