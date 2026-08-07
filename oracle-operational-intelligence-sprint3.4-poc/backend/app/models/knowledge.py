from __future__ import annotations

import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class KnowledgeResourceType(str, enum.Enum):
    DICTIONARY_VIEW = "DICTIONARY_VIEW"
    PACKAGE = "PACKAGE"
    PACKAGE_MEMBER = "PACKAGE_MEMBER"


class ChangeType(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    REMOVED = "REMOVED"
    STATUS_CHANGED = "STATUS_CHANGED"
    DDL_CHANGED = "DDL_CHANGED"
    STATS_EPOCH_CHANGED = "STATS_EPOCH_CHANGED"
    STALE_STATS_CHANGED = "STALE_STATS_CHANGED"
    ROW_ESTIMATE_CHANGED = "ROW_ESTIMATE_CHANGED"
    MODIFICATIONS_CHANGED = "MODIFICATIONS_CHANGED"
    PARTITION_COUNT_CHANGED = "PARTITION_COUNT_CHANGED"
    INDEX_STATUS_CHANGED = "INDEX_STATUS_CHANGED"


class OracleKnowledgeResource(Base):
    __tablename__ = "oracle_knowledge_resources"
    __table_args__ = (UniqueConstraint("target_id", "resource_type", "resource_name", name="uq_oracle_knowledge_resource"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id", ondelete="CASCADE"), index=True)
    resource_type: Mapped[KnowledgeResourceType] = mapped_column(Enum(KnowledgeResourceType), index=True)
    resource_name: Mapped[str] = mapped_column(String(256), index=True)
    owner_name: Mapped[str | None] = mapped_column(String(128), index=True)
    domain: Mapped[str] = mapped_column(String(80), index=True, default="General")
    privilege_tier: Mapped[int] = mapped_column(Integer, default=1, index=True)
    accessible: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class DigitalTwinObject(Base):
    __tablename__ = "digital_twin_objects"
    __table_args__ = (UniqueConstraint("target_id", "object_type", "owner_name", "object_name", name="uq_twin_object"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id", ondelete="CASCADE"), index=True)
    object_type: Mapped[str] = mapped_column(String(64), index=True)
    owner_name: Mapped[str] = mapped_column(String(128), index=True)
    object_name: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str | None] = mapped_column(String(40), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    state_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class MetadataChange(Base):
    __tablename__ = "metadata_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id", ondelete="CASCADE"), index=True)
    twin_object_id: Mapped[int | None] = mapped_column(ForeignKey("digital_twin_objects.id", ondelete="SET NULL"), index=True)
    change_type: Mapped[ChangeType] = mapped_column(Enum(ChangeType), index=True)
    object_type: Mapped[str] = mapped_column(String(64), index=True)
    owner_name: Mapped[str] = mapped_column(String(128), index=True)
    object_name: Mapped[str] = mapped_column(String(128), index=True)
    before_json: Mapped[dict | None] = mapped_column(JSON)
    after_json: Mapped[dict | None] = mapped_column(JSON)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
