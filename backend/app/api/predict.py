
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.events import get_db
from app.db.models import NetworkEvent
from app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
)
from app.services.predictor import FEATURES, predict_flow

router = APIRouter(prefix="/api/predict", tags=["Prediction"])


@router.post("", response_model=PredictionResponse)
def predict(
    request: PredictionRequest,
    db: Session = Depends(get_db),
):
    request_data = request.model_dump()

    features = {
        name: request_data[name]
        for name in FEATURES
    }

    try:
        result = predict_flow(features)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    db_event = NetworkEvent(
        flow_id=request.flow_id,
        predicted_class=result["predicted_class"],
        confidence=result["confidence"],
        source_ip=(
            str(request_data["source_ip"])
            if request_data.get("source_ip") is not None
            else None
        ),
        destination_ip=(
            str(request_data["destination_ip"])
            if request_data.get("destination_ip") is not None
            else None
        ),
        source_port=request_data.get("source_port"),
        destination_port=request_data.get("destination_port"),
        alert=result["alert"],
    )


    db.add(db_event)

    try:
        db.commit()
        db.refresh(db_event)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An event with this flow_id already exists.",
        ) from exc

    return PredictionResponse(
        flow_id=db_event.flow_id,
        predicted_class=db_event.predicted_class,
        alert=db_event.alert,
        model_status=result["model_status"],
    )
