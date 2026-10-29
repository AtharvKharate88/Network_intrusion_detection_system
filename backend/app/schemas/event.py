from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress


class EventCreate(BaseModel):
    flow_id: str = Field(min_length=1, max_length=100)
    predicted_class: str = Field(min_length=1, max_length=50)
    confidence: float = Field(ge=0.0, le=1.0)

    source_ip: IPvAnyAddress | None = None
    destination_ip: IPvAnyAddress | None = None
    source_port: int | None = Field(default=None, ge=0, le=65535)
    destination_port: int | None = Field(default=None, ge=0, le=65535)

    alert: bool = False


class EventResponse(EventCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime