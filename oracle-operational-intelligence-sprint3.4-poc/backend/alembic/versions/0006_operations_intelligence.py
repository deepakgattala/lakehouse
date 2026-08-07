"""operations intelligence
Revision ID: 0006_operations_intelligence
Revises: 0005_intelligence_engine
"""
from alembic import op
import sqlalchemy as sa

revision="0006_operations_intelligence"
down_revision="0005_intelligence_engine"
branch_labels=None
depends_on=None

plan_status=sa.Enum("PLANNED","RUNNING","COMPLETED","PARTIAL","FAILED",name="planstatus")
incident_status=sa.Enum("NEW","ACKNOWLEDGED","INVESTIGATING","MONITORING","RESOLVED","REOPENED","CLOSED",name="incidentstatus")
incident_severity=sa.Enum("INFO","WARNING","CRITICAL",name="incidentseverity")

def upgrade():
    op.create_table("collection_plans",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("target_id",sa.Integer(),sa.ForeignKey("monitoring_targets.id",ondelete="CASCADE"),nullable=False),
        sa.Column("status",plan_status,nullable=False), sa.Column("budget_seconds",sa.Integer(),nullable=False,server_default="180"),
        sa.Column("max_concurrency",sa.Integer(),nullable=False,server_default="2"), sa.Column("estimated_cost",sa.Float(),nullable=False,server_default="0"),
        sa.Column("decision_json",sa.JSON(),nullable=False), sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()), sa.Column("completed_at",sa.DateTime(timezone=True)))
    op.create_index("ix_collection_plans_target_id","collection_plans",["target_id"]); op.create_index("ix_collection_plans_status","collection_plans",["status"])
    op.create_table("collection_plan_items",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("plan_id",sa.Integer(),sa.ForeignKey("collection_plans.id",ondelete="CASCADE"),nullable=False),
        sa.Column("collector_key",sa.String(120),nullable=False), sa.Column("action",sa.String(40),nullable=False), sa.Column("priority",sa.Integer(),nullable=False,server_default="50"),
        sa.Column("reason",sa.Text(),nullable=False), sa.Column("estimated_seconds",sa.Float(),nullable=False,server_default="0"), sa.Column("resource_filter",sa.JSON(),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index("ix_collection_plan_items_plan_id","collection_plan_items",["plan_id"])
    op.create_table("correlation_rules",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("rule_key",sa.String(150),nullable=False,unique=True), sa.Column("display_name",sa.String(200),nullable=False),
        sa.Column("enabled",sa.Boolean(),nullable=False,server_default=sa.true()), sa.Column("window_minutes",sa.Integer(),nullable=False,server_default="60"),
        sa.Column("conditions_json",sa.JSON(),nullable=False), sa.Column("incident_type",sa.String(100),nullable=False), sa.Column("severity",incident_severity,nullable=False),
        sa.Column("confidence",sa.Float(),nullable=False,server_default="0.8"), sa.Column("runbook_key",sa.String(150)), sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_table("incidents",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("target_id",sa.Integer(),sa.ForeignKey("monitoring_targets.id",ondelete="CASCADE"),nullable=False),
        sa.Column("twin_object_id",sa.Integer(),sa.ForeignKey("digital_twin_objects.id",ondelete="SET NULL")), sa.Column("incident_key",sa.String(220),nullable=False),
        sa.Column("incident_type",sa.String(120),nullable=False), sa.Column("title",sa.String(300),nullable=False), sa.Column("severity",incident_severity,nullable=False),
        sa.Column("status",incident_status,nullable=False), sa.Column("confidence",sa.Float(),nullable=False,server_default="0.5"), sa.Column("root_cause_summary",sa.Text()),
        sa.Column("correlation_json",sa.JSON(),nullable=False), sa.Column("first_seen_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
        sa.Column("last_seen_at",sa.DateTime(timezone=True),server_default=sa.func.now()), sa.Column("acknowledged_at",sa.DateTime(timezone=True)), sa.Column("resolved_at",sa.DateTime(timezone=True)))
    op.create_index("ix_incidents_target_status","incidents",["target_id","status"]); op.create_index("ix_incidents_object","incidents",["twin_object_id"])
    op.create_table("incident_events",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("incident_id",sa.Integer(),sa.ForeignKey("incidents.id",ondelete="CASCADE"),nullable=False),
        sa.Column("event_type",sa.String(120),nullable=False), sa.Column("source_type",sa.String(80),nullable=False), sa.Column("source_id",sa.Integer()),
        sa.Column("title",sa.String(300),nullable=False), sa.Column("detail_json",sa.JSON(),nullable=False), sa.Column("occurred_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index("ix_incident_events_incident_id","incident_events",["incident_id"])
    op.create_table("runbooks",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("runbook_key",sa.String(150),nullable=False,unique=True), sa.Column("display_name",sa.String(220),nullable=False),
        sa.Column("description",sa.Text(),nullable=False), sa.Column("owner_type",sa.String(80),nullable=False,server_default="DBA"), sa.Column("steps_json",sa.JSON(),nullable=False),
        sa.Column("references_json",sa.JSON(),nullable=False), sa.Column("enabled",sa.Boolean(),nullable=False,server_default=sa.true()), sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_table("object_timeline_events",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("target_id",sa.Integer(),sa.ForeignKey("monitoring_targets.id",ondelete="CASCADE"),nullable=False),
        sa.Column("twin_object_id",sa.Integer(),sa.ForeignKey("digital_twin_objects.id",ondelete="CASCADE"),nullable=False), sa.Column("event_type",sa.String(120),nullable=False),
        sa.Column("source_type",sa.String(80),nullable=False), sa.Column("source_id",sa.Integer()), sa.Column("title",sa.String(300),nullable=False), sa.Column("detail_json",sa.JSON(),nullable=False),
        sa.Column("occurred_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index("ix_object_timeline_object_time","object_timeline_events",["twin_object_id","occurred_at"])

def downgrade():
    op.drop_table("object_timeline_events"); op.drop_table("runbooks"); op.drop_table("incident_events"); op.drop_table("incidents"); op.drop_table("correlation_rules"); op.drop_table("collection_plan_items"); op.drop_table("collection_plans")
    incident_status.drop(op.get_bind(),checkfirst=False); incident_severity.drop(op.get_bind(),checkfirst=False); plan_status.drop(op.get_bind(),checkfirst=False)
