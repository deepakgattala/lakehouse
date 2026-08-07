import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MetricValueType(str, enum.Enum):
    GAUGE = "GAUGE"
    COUNTER = "COUNTER"
    STATE = "STATE"


class MetricEventStatus(str, enum.Enum):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    metric_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80), index=True)
    unit: Mapped[str] = mapped_column(String(40), default="count")
    value_type: Mapped[MetricValueType] = mapped_column(Enum(MetricValueType), default=MetricValueType.GAUGE)
    default_retention_days: Mapped[int] = mapped_column(Integer, default=365)
    allowed_tags: Mapped[list] = mapped_column(JSON, default=list)
    source_collectors: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MetricSample(Base):
    __tablename__ = "metric_samples"
    __table_args__ = (
        Index("ix_metric_samples_metric_time", "metric_key", "observed_at"),
        Index("ix_metric_samples_target_time", "target_id", "observed_at"),
        Index("ix_metric_samples_resource_time", "resource_key", "observed_at"),
    )

    # TimescaleDB requires unique constraints to include the partitioning column.
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    metric_key: Mapped[str] = mapped_column(String(180), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id", ondelete="CASCADE"), index=True)
    collector_run_id: Mapped[int | None] = mapped_column(ForeignKey("collector_runs.id", ondelete="SET NULL"), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), default="database")
    resource_key: Mapped[str] = mapped_column(String(500), index=True)
    numeric_value: Mapped[float | None] = mapped_column(Float)
    state_value: Mapped[str | None] = mapped_column(String(255))
    unit: Mapped[str] = mapped_column(String(40), default="count")
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    dimensions_hash: Mapped[str] = mapped_column(String(64), index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MetricEvent(Base):
    """Durable outbox for collector -> metric-pipeline handoff."""
    __tablename__ = "metric_events"
    __table_args__ = (
        Index("ix_metric_events_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type: Mapped[str] = mapped_column(String(80), default="METRIC_OBSERVED")
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id", ondelete="CASCADE"), index=True)
    collector_run_id: Mapped[int | None] = mapped_column(ForeignKey("collector_runs.id", ondelete="SET NULL"), index=True)
    metric_key: Mapped[str] = mapped_column(String(180), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[MetricEventStatus] = mapped_column(Enum(MetricEventStatus), default=MetricEventStatus.PENDING, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
