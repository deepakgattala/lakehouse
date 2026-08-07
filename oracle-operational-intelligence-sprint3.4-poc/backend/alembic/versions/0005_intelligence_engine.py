"""rules, evidence, recommendations and health intelligence"""
from alembic import op
import sqlalchemy as sa
revision = "0005_intelligence_engine"
down_revision = "0004_oracle_knowledge_engine"
branch_labels = None
depends_on = None
rule_severity = sa.Enum("INFO","WARNING","CRITICAL", name="ruleseverity")
health_state = sa.Enum("HEALTHY","WATCH","WARNING","CRITICAL","UNKNOWN", name="objecthealthstate")

def upgrade():
    rule_severity.create(op.get_bind(), checkfirst=True); health_state.create(op.get_bind(), checkfirst=True)
    op.create_table("rule_definitions",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("rule_key",sa.String(150),nullable=False,unique=True),
        sa.Column("display_name",sa.String(200),nullable=False), sa.Column("domain",sa.String(80),nullable=False),
        sa.Column("description",sa.Text(),nullable=False), sa.Column("enabled",sa.Boolean(),nullable=False),
        sa.Column("current_version",sa.Integer(),nullable=False), sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
        sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index("ix_rule_definitions_rule_key","rule_definitions",["rule_key"]); op.create_index("ix_rule_definitions_domain","rule_definitions",["domain"])
    op.create_table("rule_versions",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("rule_definition_id",sa.Integer(),sa.ForeignKey("rule_definitions.id",ondelete="CASCADE"),nullable=False),
        sa.Column("version",sa.Integer(),nullable=False),sa.Column("object_types",sa.JSON(),nullable=False),sa.Column("condition_json",sa.JSON(),nullable=False),
        sa.Column("risk_weight",sa.Float(),nullable=False),sa.Column("severity",rule_severity,nullable=False),sa.Column("confidence",sa.Float(),nullable=False),
        sa.Column("evidence_template",sa.JSON(),nullable=False),sa.Column("recommendation_template",sa.JSON(),nullable=False),sa.Column("documentation_refs",sa.JSON(),nullable=False),
        sa.Column("created_by",sa.Integer(),sa.ForeignKey("users.id")),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
        sa.UniqueConstraint("rule_definition_id","version",name="uq_rule_version"))
    op.create_index("ix_rule_versions_rule_definition_id","rule_versions",["rule_definition_id"])
    op.create_table("rule_executions",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("target_id",sa.Integer(),sa.ForeignKey("monitoring_targets.id",ondelete="CASCADE"),nullable=False),
        sa.Column("twin_object_id",sa.Integer(),sa.ForeignKey("digital_twin_objects.id",ondelete="CASCADE"),nullable=False),
        sa.Column("rule_definition_id",sa.Integer(),sa.ForeignKey("rule_definitions.id",ondelete="CASCADE"),nullable=False),sa.Column("rule_version",sa.Integer(),nullable=False),
        sa.Column("matched",sa.Boolean(),nullable=False),sa.Column("score_delta",sa.Float(),nullable=False),sa.Column("confidence",sa.Float(),nullable=False),
        sa.Column("evaluation_json",sa.JSON(),nullable=False),sa.Column("executed_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    for c in ["target_id","twin_object_id","rule_definition_id","matched","executed_at"]: op.create_index(f"ix_rule_executions_{c}","rule_executions",[c])
    op.create_table("intelligence_evidence",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("target_id",sa.Integer(),sa.ForeignKey("monitoring_targets.id",ondelete="CASCADE"),nullable=False),
        sa.Column("twin_object_id",sa.Integer(),sa.ForeignKey("digital_twin_objects.id",ondelete="CASCADE"),nullable=False),sa.Column("rule_execution_id",sa.Integer(),sa.ForeignKey("rule_executions.id",ondelete="SET NULL")),
        sa.Column("evidence_type",sa.String(100),nullable=False),sa.Column("title",sa.String(250),nullable=False),sa.Column("detail_json",sa.JSON(),nullable=False),sa.Column("confidence",sa.Float(),nullable=False),
        sa.Column("observed_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    for c in ["target_id","twin_object_id","rule_execution_id","evidence_type","observed_at"]: op.create_index(f"ix_intelligence_evidence_{c}","intelligence_evidence",[c])
    op.create_table("recommendations",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("target_id",sa.Integer(),sa.ForeignKey("monitoring_targets.id",ondelete="CASCADE"),nullable=False),
        sa.Column("twin_object_id",sa.Integer(),sa.ForeignKey("digital_twin_objects.id",ondelete="CASCADE"),nullable=False),sa.Column("rule_execution_id",sa.Integer(),sa.ForeignKey("rule_executions.id",ondelete="SET NULL")),
        sa.Column("action_key",sa.String(120),nullable=False),sa.Column("priority",sa.String(40),nullable=False),sa.Column("title",sa.String(250),nullable=False),sa.Column("rationale",sa.Text(),nullable=False),
        sa.Column("owner_type",sa.String(80),nullable=False),sa.Column("required_privilege",sa.String(120),nullable=False),sa.Column("runbook_json",sa.JSON(),nullable=False),sa.Column("status",sa.String(40),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    for c in ["target_id","twin_object_id","rule_execution_id","action_key","priority","status","created_at"]: op.create_index(f"ix_recommendations_{c}","recommendations",[c])
    op.create_table("health_scores",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("target_id",sa.Integer(),sa.ForeignKey("monitoring_targets.id",ondelete="CASCADE"),nullable=False),
        sa.Column("twin_object_id",sa.Integer(),sa.ForeignKey("digital_twin_objects.id",ondelete="CASCADE"),nullable=False),sa.Column("domain",sa.String(80),nullable=False),
        sa.Column("score",sa.Float(),nullable=False),sa.Column("risk_score",sa.Float(),nullable=False),sa.Column("confidence",sa.Float(),nullable=False),sa.Column("factors_json",sa.JSON(),nullable=False),
        sa.Column("calculated_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    for c in ["target_id","twin_object_id","domain","calculated_at"]: op.create_index(f"ix_health_scores_{c}","health_scores",[c])
    op.create_table("object_state_transitions",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("target_id",sa.Integer(),sa.ForeignKey("monitoring_targets.id",ondelete="CASCADE"),nullable=False),
        sa.Column("twin_object_id",sa.Integer(),sa.ForeignKey("digital_twin_objects.id",ondelete="CASCADE"),nullable=False),sa.Column("previous_state",health_state,nullable=False),sa.Column("new_state",health_state,nullable=False),
        sa.Column("reason_json",sa.JSON(),nullable=False),sa.Column("transitioned_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    for c in ["target_id","twin_object_id","new_state","transitioned_at"]: op.create_index(f"ix_object_state_transitions_{c}","object_state_transitions",[c])

def downgrade():
    for t in ["object_state_transitions","health_scores","recommendations","intelligence_evidence","rule_executions","rule_versions","rule_definitions"]: op.drop_table(t)
    health_state.drop(op.get_bind(), checkfirst=True); rule_severity.drop(op.get_bind(), checkfirst=True)
