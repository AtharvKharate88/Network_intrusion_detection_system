from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class NetworkEvent(Base):
    __tablename__ = "network_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    flow_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
    )

    predicted_class: Mapped[str] = mapped_column(
        String(50),
        index=True,
    )

    confidence: Mapped[float] = mapped_column(Float)

    source_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    destination_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    source_port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    destination_port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    alert: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

class BehavioralAlert(Base):
    __tablename__ = "behavioral_alerts"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )

    alert_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True
    )

    alert_type: Mapped[str] = mapped_column(String(50))

    source_ip: Mapped[str] = mapped_column(String(45))
    destination_ip: Mapped[str] = mapped_column(String(45))

    distinct_ports: Mapped[int] = mapped_column(Integer)
    destination_ports: Mapped[list] = mapped_column(JSON)
    window_seconds: Mapped[int] = mapped_column(Integer)

    detection_method: Mapped[str] = mapped_column(String(30))
    capture_file: Mapped[str] = mapped_column(String(255))
    session_id: Mapped[str] = mapped_column(String(100), index=True)

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
