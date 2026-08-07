"""maintenance actions
Revision ID: 0007_maintenance_actions
Revises: 0006_operations_intelligence
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_maintenance_actions"
down_revision = "0006_operations_intelligence"
branch_labels = None
depends_on = None

action_enum = sa.Enum("GATHER_TABLE_STATS","GATHER_SCHEMA_STATS","GATHER_INDEX_STATS","REBUILD_INDEX", name="maintenanceaction")
status_enum = sa.Enum("QUEUED","RUNNING","SUCCEEDED","FAILED","CANCELLED","DRY_RUN", name="maintenancestatus")

def upgrade():
    op.create_table(
        "maintenance_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target_id", sa.Integer(), sa.ForeignKey("monitoring_targets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", action_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("owner_name", sa.String(128), nullable=False),
        sa.Column("object_name", sa.String(128)),
        sa.Column("options_json", sa.JSON(), nullable=False),
        sa.Column("preview_text", sa.Text(), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_maintenance_jobs_target_id", "maintenance_jobs", ["target_id"])
    op.create_index("ix_maintenance_jobs_action", "maintenance_jobs", ["action"])
    op.create_index("ix_maintenance_jobs_status", "maintenance_jobs", ["status"])
    op.create_index("ix_maintenance_jobs_created_at", "maintenance_jobs", ["created_at"])

def downgrade():
    op.drop_table("maintenance_jobs")
    status_enum.drop(op.get_bind(), checkfirst=False)
    action_enum.drop(op.get_bind(), checkfirst=False)
