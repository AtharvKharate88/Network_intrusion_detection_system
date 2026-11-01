
import math

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, model_validator


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    flow_id: str = Field(min_length=1, max_length=100)
    source_ip: IPvAnyAddress | None = None
    destination_ip: IPvAnyAddress | None = None
    source_port: int | None = Field(default=None, ge=0, le=65535)
    destination_port: int | None = Field(default=None, ge=0, le=65535)

    @model_validator(mode="after")
    def validate_model_features(self):
        from app.services.predictor import FEATURES

        data = self.model_dump()
        missing = [
            name for name in FEATURES
            if name not in data
        ]

        if missing:
            raise ValueError(
                f"Missing {len(missing)} model features. "
                f"First missing features: {missing[:5]}"
            )

        for name in FEATURES:
            value = data[name]

            if isinstance(value, bool) or not isinstance(
                value, (int, float)
            ):
                raise ValueError(
                    f"Feature '{name}' must be numeric."
                )
            if not math.isfinite(value):
                raise ValueError(
                    f"Feature '{name}' must be finite."
                )

        return self


class PredictionResponse(BaseModel):
    flow_id: str
    predicted_class: str
    alert: bool
    model_status: str
