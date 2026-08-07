from __future__ import annotations
import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class PlanStatus(str, enum.Enum):
    PLANNED="PLANNED"; RUNNING="RUNNING"; COMPLETED="COMPLETED"; PARTIAL="PARTIAL"; FAILED="FAILED"

class IncidentStatus(str, enum.Enum):
    NEW="NEW"; ACKNOWLEDGED="ACKNOWLEDGED"; INVESTIGATING="INVESTIGATING"; MONITORING="MONITORING"; RESOLVED="RESOLVED"; REOPENED="REOPENED"; CLOSED="CLOSED"

class IncidentSeverity(str, enum.Enum):
    INFO="INFO"; WARNING="WARNING"; CRITICAL="CRITICAL"

class CollectionPlan(Base):
    __tablename__="collection_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id",ondelete="CASCADE"),index=True)
    status: Mapped[PlanStatus] = mapped_column(Enum(PlanStatus),default=PlanStatus.PLANNED,index=True)
    budget_seconds: Mapped[int] = mapped_column(Integer,default=180)
    max_concurrency: Mapped[int] = mapped_column(Integer,default=2)
    estimated_cost: Mapped[float] = mapped_column(Float,default=0)
    decision_json: Mapped[dict] = mapped_column(JSON,default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)
    completed_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True))

class CollectionPlanItem(Base):
    __tablename__="collection_plan_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("collection_plans.id",ondelete="CASCADE"),index=True)
    collector_key: Mapped[str] = mapped_column(String(120),index=True)
    action: Mapped[str] = mapped_column(String(40),index=True) # RUN/SKIP/DEFER/DEEP
    priority: Mapped[int] = mapped_column(Integer,default=50,index=True)
    reason: Mapped[str] = mapped_column(Text)
    estimated_seconds: Mapped[float] = mapped_column(Float,default=0)
    resource_filter: Mapped[dict] = mapped_column(JSON,default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())

class CorrelationRule(Base):
    __tablename__="correlation_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    rule_key: Mapped[str] = mapped_column(String(150),unique=True,index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean,default=True,index=True)
    window_minutes: Mapped[int] = mapped_column(Integer,default=60)
    conditions_json: Mapped[dict] = mapped_column(JSON,default=dict)
    incident_type: Mapped[str] = mapped_column(String(100),index=True)
    severity: Mapped[IncidentSeverity] = mapped_column(Enum(IncidentSeverity),default=IncidentSeverity.WARNING)
    confidence: Mapped[float] = mapped_column(Float,default=.8)
    runbook_key: Mapped[str|None] = mapped_column(String(150),index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())

class Incident(Base):
    __tablename__="incidents"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id",ondelete="CASCADE"),index=True)
    twin_object_id: Mapped[int|None] = mapped_column(ForeignKey("digital_twin_objects.id",ondelete="SET NULL"),index=True)
    incident_key: Mapped[str] = mapped_column(String(220),index=True)
    incident_type: Mapped[str] = mapped_column(String(120),index=True)
    title: Mapped[str] = mapped_column(String(300))
    severity: Mapped[IncidentSeverity] = mapped_column(Enum(IncidentSeverity),index=True)
    status: Mapped[IncidentStatus] = mapped_column(Enum(IncidentStatus),default=IncidentStatus.NEW,index=True)
    confidence: Mapped[float] = mapped_column(Float,default=.5)
    root_cause_summary: Mapped[str|None] = mapped_column(Text)
    correlation_json: Mapped[dict] = mapped_column(JSON,default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)
    acknowledged_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True))

class IncidentEvent(Base):
    __tablename__="incident_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id",ondelete="CASCADE"),index=True)
    event_type: Mapped[str] = mapped_column(String(120),index=True)
    source_type: Mapped[str] = mapped_column(String(80),index=True)
    source_id: Mapped[int|None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    detail_json: Mapped[dict] = mapped_column(JSON,default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)

class Runbook(Base):
    __tablename__="runbooks"
    id: Mapped[int] = mapped_column(primary_key=True)
    runbook_key: Mapped[str] = mapped_column(String(150),unique=True,index=True)
    display_name: Mapped[str] = mapped_column(String(220))
    description: Mapped[str] = mapped_column(Text)
    owner_type: Mapped[str] = mapped_column(String(80),default="DBA")
    steps_json: Mapped[list] = mapped_column(JSON,default=list)
    references_json: Mapped[list] = mapped_column(JSON,default=list)
    enabled: Mapped[bool] = mapped_column(Boolean,default=True,index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())

class ObjectTimelineEvent(Base):
    __tablename__="object_timeline_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitoring_targets.id",ondelete="CASCADE"),index=True)
    twin_object_id: Mapped[int] = mapped_column(ForeignKey("digital_twin_objects.id",ondelete="CASCADE"),index=True)
    event_type: Mapped[str] = mapped_column(String(120),index=True)
    source_type: Mapped[str] = mapped_column(String(80),index=True)
    source_id: Mapped[int|None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    detail_json: Mapped[dict] = mapped_column(JSON,default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)
