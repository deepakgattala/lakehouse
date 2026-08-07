import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class CapabilityStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    ACCESS_DENIED = "ACCESS_DENIED"
    NOT_PRESENT = "NOT_PRESENT"
    TEST_FAILED = "TEST_FAILED"
    DISABLED = "DISABLED"

class RunStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"

class MonitoringTarget(Base):
    __tablename__ = "monitoring_targets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    environment: Mapped[str] = mapped_column(String(40), index=True)
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=1521)
    service_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str] = mapped_column(String(255))
    secret_reference: Mapped[str] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    connection_timeout_seconds: Mapped[int] = mapped_column(Integer, default=10)
    query_timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    max_pool_size: Mapped[int] = mapped_column(Integer, default=2)
    max_concurrent_jobs: Mapped[int] = mapped_column(Integer, default=2)
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    last_connection_status: Mapped[str | None] = mapped_column(String(40))
    last_connection_ms: Mapped[int | None] = mapped_column(Integer)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    capabilities: Mapped[list["TargetCapability"]] = relationship(back_populates="target", cascade="all, delete-orphan")
    collector_configs: Mapped[list["CollectorConfig"]] = relationship(back_populates="target", cascade="all, delete-orphan")

class TargetCapability(Base):
    __tablename__ = "target_capabilities"
    __table_args__ = (UniqueConstraint("target_id", "capability_key", name="uq_target_capability"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id", ondelete="CASCADE"), index=True)
    capability_key: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[CapabilityStatus] = mapped_column(Enum(CapabilityStatus), default=CapabilityStatus.TEST_FAILED)
    detail: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    target: Mapped[MonitoringTarget] = relationship(back_populates="capabilities")

class CollectorDefinition(Base):
    __tablename__ = "collector_definitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    collector_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(40), default="1.0")
    required_capabilities: Mapped[list] = mapped_column(JSON, default=list)
    default_schedule: Mapped[str] = mapped_column(String(100), default="0 * * * *")
    default_timeout_seconds: Mapped[int] = mapped_column(Integer, default=60)
    configuration_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class CollectorConfig(Base):
    __tablename__ = "collector_configs"
    __table_args__ = (UniqueConstraint("target_id", "collector_definition_id", name="uq_target_collector"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id", ondelete="CASCADE"), index=True)
    collector_definition_id: Mapped[int] = mapped_column(ForeignKey("collector_definitions.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_expression: Mapped[str] = mapped_column(String(100))
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60)
    retry_count: Mapped[int] = mapped_column(Integer, default=1)
    config_version: Mapped[int] = mapped_column(Integer, default=1)
    configuration_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    target: Mapped[MonitoringTarget] = relationship(back_populates="collector_configs")
    definition: Mapped[CollectorDefinition] = relationship()

class CollectorConfigVersion(Base):
    __tablename__ = "collector_config_versions"
    __table_args__ = (UniqueConstraint("collector_config_id", "version", name="uq_collector_config_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    collector_config_id: Mapped[int] = mapped_column(ForeignKey("collector_configs.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    change_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class CollectorRun(Base):
    __tablename__ = "collector_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id", ondelete="CASCADE"), index=True)
    collector_config_id: Mapped[int | None] = mapped_column(ForeignKey("collector_configs.id", ondelete="SET NULL"), index=True)
    collector_key: Mapped[str] = mapped_column(String(100), index=True)
    config_version: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.QUEUED, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    records_collected: Mapped[int] = mapped_column(Integer, default=0)
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
