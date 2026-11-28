from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel, ConfigDict, Field,
    IPvAnyAddress, AwareDatetime, model_validator
)

Port = Annotated[int, Field(ge=0, le=65535)]


class BehavioralAlertCreate(BaseModel):
    alert_id: str = Field(min_length=1, max_length=100)
    alert_type: Literal["Suspected Port Scan"]

    source_ip: IPvAnyAddress
    destination_ip: IPvAnyAddress

    distinct_ports: int = Field(ge=2, le=65536)
    destination_ports: list[Port] = Field(
        min_length=2, max_length=65536
    )
    window_seconds: int = Field(ge=1, le=3600)

    detection_method: Literal["behavioral"]
    capture_file: str = Field(min_length=1, max_length=255)
    session_id: str = Field(min_length=1, max_length=100)

    observed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_ports(self):
        unique_ports = set(self.destination_ports)

        if len(unique_ports) != len(self.destination_ports):
            raise ValueError("Duplicate destination ports")

        if len(unique_ports) != self.distinct_ports:
            raise ValueError("Distinct port count mismatch")

        return self


class BehavioralAlertResponse(BehavioralAlertCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
