"""sprint 3.1 metric registry and durable event pipeline"""
from alembic import op
import sqlalchemy as sa

revision = "0003_metric_pipeline"
down_revision = "0002_monitoring_configuration"
branch_labels = None
depends_on = None

metric_value_type = sa.Enum("GAUGE", "COUNTER", "STATE", name="metricvaluetype")
metric_event_status = sa.Enum("PENDING", "PUBLISHED", "FAILED", name="metriceventstatus")


def upgrade():
    metric_value_type.create(op.get_bind(), checkfirst=True)
    metric_event_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "metric_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("metric_key", sa.String(180), nullable=False),
        sa.Column("display_name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("value_type", metric_value_type, nullable=False),
        sa.Column("default_retention_days", sa.Integer(), nullable=False),
        sa.Column("allowed_tags", sa.JSON(), nullable=False),
        sa.Column("source_collectors", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("metric_key"),
    )
    op.create_index("ix_metric_definitions_metric_key", "metric_definitions", ["metric_key"])
    op.create_index("ix_metric_definitions_category", "metric_definitions", ["category"])

    op.create_table(
        "metric_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("target_id", sa.Integer(), sa.ForeignKey("monitoring_targets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("collector_run_id", sa.Integer(), sa.ForeignKey("collector_runs.id", ondelete="SET NULL")),
        sa.Column("metric_key", sa.String(180), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", metric_event_status, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_metric_events_target_id", "metric_events", ["target_id"])
    op.create_index("ix_metric_events_collector_run_id", "metric_events", ["collector_run_id"])
    op.create_index("ix_metric_events_metric_key", "metric_events", ["metric_key"])
    op.create_index("ix_metric_events_status", "metric_events", ["status"])
    op.create_index("ix_metric_events_status_created", "metric_events", ["status", "created_at"])

    op.create_table(
        "metric_samples",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_key", sa.String(180), nullable=False),
        sa.Column("target_id", sa.Integer(), sa.ForeignKey("monitoring_targets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("collector_run_id", sa.Integer(), sa.ForeignKey("collector_runs.id", ondelete="SET NULL")),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_key", sa.String(500), nullable=False),
        sa.Column("numeric_value", sa.Float()),
        sa.Column("state_value", sa.String(255)),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("dimensions_hash", sa.String(64), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", "observed_at", name="pk_metric_samples"),
    )
    op.create_index("ix_metric_samples_metric_key", "metric_samples", ["metric_key"])
    op.create_index("ix_metric_samples_target_id", "metric_samples", ["target_id"])
    op.create_index("ix_metric_samples_collector_run_id", "metric_samples", ["collector_run_id"])
    op.create_index("ix_metric_samples_resource_key", "metric_samples", ["resource_key"])
    op.create_index("ix_metric_samples_dimensions_hash", "metric_samples", ["dimensions_hash"])
    op.create_index("ix_metric_samples_metric_time", "metric_samples", ["metric_key", "observed_at"])
    op.create_index("ix_metric_samples_target_time", "metric_samples", ["target_id", "observed_at"])
    op.create_index("ix_metric_samples_resource_time", "metric_samples", ["resource_key", "observed_at"])

    # Idempotent on the Timescale image; keeps ordinary PostgreSQL compatibility if extension is unavailable.
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute("SELECT create_hypertable('metric_samples', 'observed_at', if_not_exists => TRUE)")


def downgrade():
    op.drop_table("metric_samples")
    op.drop_table("metric_events")
    op.drop_table("metric_definitions")
    metric_event_status.drop(op.get_bind(), checkfirst=True)
    metric_value_type.drop(op.get_bind(), checkfirst=True)
