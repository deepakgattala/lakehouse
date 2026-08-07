from __future__ import annotations
import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class MaintenanceAction(str, enum.Enum):
    GATHER_TABLE_STATS = "GATHER_TABLE_STATS"
    GATHER_SCHEMA_STATS = "GATHER_SCHEMA_STATS"
    GATHER_INDEX_STATS = "GATHER_INDEX_STATS"
    REBUILD_INDEX = "REBUILD_INDEX"

class MaintenanceStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DRY_RUN = "DRY_RUN"

class MaintenanceJob(Base):
    __tablename__ = "maintenance_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id", ondelete="CASCADE"), index=True)
    action: Mapped[MaintenanceAction] = mapped_column(Enum(MaintenanceAction), index=True)
    status: Mapped[MaintenanceStatus] = mapped_column(Enum(MaintenanceStatus), default=MaintenanceStatus.QUEUED, index=True)
    owner_name: Mapped[str] = mapped_column(String(128), index=True)
    object_name: Mapped[str | None] = mapped_column(String(128), index=True)
    options_json: Mapped[dict] = mapped_column(JSON, default=dict)
    preview_text: Mapped[str] = mapped_column(Text)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
