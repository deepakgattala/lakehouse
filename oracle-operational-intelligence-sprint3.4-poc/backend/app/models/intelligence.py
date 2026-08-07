from __future__ import annotations
import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class RuleSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ObjectHealthState(str, enum.Enum):
    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class RuleDefinition(Base):
    __tablename__ = "rule_definitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    rule_key: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RuleVersion(Base):
    __tablename__ = "rule_versions"
    __table_args__ = (UniqueConstraint("rule_definition_id", "version", name="uq_rule_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    rule_definition_id: Mapped[int] = mapped_column(ForeignKey("rule_definitions.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    object_types: Mapped[list] = mapped_column(JSON, default=list)
    condition_json: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_weight: Mapped[float] = mapped_column(Float, default=0.0)
    severity: Mapped[RuleSeverity] = mapped_column(Enum(RuleSeverity), default=RuleSeverity.WARNING)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    evidence_template: Mapped[dict] = mapped_column(JSON, default=dict)
    recommendation_template: Mapped[dict] = mapped_column(JSON, default=dict)
    documentation_refs: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RuleExecution(Base):
    __tablename__ = "rule_executions"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id", ondelete="CASCADE"), index=True)
    twin_object_id: Mapped[int] = mapped_column(ForeignKey("digital_twin_objects.id", ondelete="CASCADE"), index=True)
    rule_definition_id: Mapped[int] = mapped_column(ForeignKey("rule_definitions.id", ondelete="CASCADE"), index=True)
    rule_version: Mapped[int] = mapped_column(Integer)
    matched: Mapped[bool] = mapped_column(Boolean, index=True)
    score_delta: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evaluation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Evidence(Base):
    __tablename__ = "intelligence_evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id", ondelete="CASCADE"), index=True)
    twin_object_id: Mapped[int] = mapped_column(ForeignKey("digital_twin_objects.id", ondelete="CASCADE"), index=True)
    rule_execution_id: Mapped[int | None] = mapped_column(ForeignKey("rule_executions.id", ondelete="SET NULL"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(250))
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id", ondelete="CASCADE"), index=True)
    twin_object_id: Mapped[int] = mapped_column(ForeignKey("digital_twin_objects.id", ondelete="CASCADE"), index=True)
    rule_execution_id: Mapped[int | None] = mapped_column(ForeignKey("rule_executions.id", ondelete="SET NULL"), index=True)
    action_key: Mapped[str] = mapped_column(String(120), index=True)
    priority: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(250))
    rationale: Mapped[str] = mapped_column(Text)
    owner_type: Mapped[str] = mapped_column(String(80), default="DBA")
    required_privilege: Mapped[str] = mapped_column(String(120), default="READ_ONLY")
    runbook_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class HealthScore(Base):
    __tablename__ = "health_scores"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id", ondelete="CASCADE"), index=True)
    twin_object_id: Mapped[int] = mapped_column(ForeignKey("digital_twin_objects.id", ondelete="CASCADE"), index=True)
    domain: Mapped[str] = mapped_column(String(80), index=True)
    score: Mapped[float] = mapped_column(Float)
    risk_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    factors_json: Mapped[list] = mapped_column(JSON, default=list)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ObjectStateTransition(Base):
    __tablename__ = "object_state_transitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id", ondelete="CASCADE"), index=True)
    twin_object_id: Mapped[int] = mapped_column(ForeignKey("digital_twin_objects.id", ondelete="CASCADE"), index=True)
    previous_state: Mapped[ObjectHealthState] = mapped_column(Enum(ObjectHealthState), default=ObjectHealthState.UNKNOWN)
    new_state: Mapped[ObjectHealthState] = mapped_column(Enum(ObjectHealthState), index=True)
    reason_json: Mapped[dict] = mapped_column(JSON, default=dict)
    transitioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
