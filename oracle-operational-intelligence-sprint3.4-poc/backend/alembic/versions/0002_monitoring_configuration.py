"""phase 2 monitoring configuration"""
from alembic import op
import sqlalchemy as sa
revision="0002_monitoring_configuration"
down_revision="0001_foundation"
branch_labels=None
depends_on=None
capability_enum=sa.Enum("AVAILABLE","ACCESS_DENIED","NOT_PRESENT","TEST_FAILED","DISABLED",name="capabilitystatus")
run_enum=sa.Enum("QUEUED","RUNNING","SUCCEEDED","PARTIAL","FAILED",name="runstatus")

def upgrade():
    capability_enum.create(op.get_bind(), checkfirst=True); run_enum.create(op.get_bind(), checkfirst=True)
    op.create_table("monitoring_targets",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("name",sa.String(120),nullable=False),sa.Column("environment",sa.String(40),nullable=False),
      sa.Column("host",sa.String(255),nullable=False),sa.Column("port",sa.Integer(),nullable=False),sa.Column("service_name",sa.String(255),nullable=False),
      sa.Column("username",sa.String(255),nullable=False),sa.Column("secret_reference",sa.String(500),nullable=False),sa.Column("enabled",sa.Boolean(),nullable=False),
      sa.Column("connection_timeout_seconds",sa.Integer(),nullable=False),sa.Column("query_timeout_seconds",sa.Integer(),nullable=False),sa.Column("max_pool_size",sa.Integer(),nullable=False),
      sa.Column("max_concurrent_jobs",sa.Integer(),nullable=False),sa.Column("tags",sa.JSON(),nullable=False),sa.Column("notes",sa.Text()),
      sa.Column("last_connection_status",sa.String(40)),sa.Column("last_connection_ms",sa.Integer()),sa.Column("last_checked_at",sa.DateTime(timezone=True)),
      sa.Column("created_by",sa.Integer(),sa.ForeignKey("users.id")),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
      sa.UniqueConstraint("name"))
    op.create_index("ix_monitoring_targets_name","monitoring_targets",["name"]); op.create_index("ix_monitoring_targets_environment","monitoring_targets",["environment"])
    op.create_table("target_capabilities",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("target_id",sa.Integer(),sa.ForeignKey("monitoring_targets.id",ondelete="CASCADE"),nullable=False),
      sa.Column("capability_key",sa.String(100),nullable=False),sa.Column("status",capability_enum,nullable=False),sa.Column("detail",sa.Text()),sa.Column("last_checked_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
      sa.UniqueConstraint("target_id","capability_key",name="uq_target_capability"))
    op.create_index("ix_target_capabilities_target_id","target_capabilities",["target_id"]); op.create_index("ix_target_capabilities_capability_key","target_capabilities",["capability_key"])
    op.create_table("collector_definitions",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("collector_key",sa.String(100),nullable=False),sa.Column("display_name",sa.String(150),nullable=False),sa.Column("category",sa.String(80),nullable=False),
      sa.Column("description",sa.Text(),nullable=False),sa.Column("version",sa.String(40),nullable=False),sa.Column("required_capabilities",sa.JSON(),nullable=False),sa.Column("default_schedule",sa.String(100),nullable=False),
      sa.Column("default_timeout_seconds",sa.Integer(),nullable=False),sa.Column("configuration_schema",sa.JSON(),nullable=False),sa.Column("enabled",sa.Boolean(),nullable=False),sa.UniqueConstraint("collector_key"))
    op.create_index("ix_collector_definitions_collector_key","collector_definitions",["collector_key"]); op.create_index("ix_collector_definitions_category","collector_definitions",["category"])
    op.create_table("collector_configs",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("target_id",sa.Integer(),sa.ForeignKey("monitoring_targets.id",ondelete="CASCADE"),nullable=False),sa.Column("collector_definition_id",sa.Integer(),sa.ForeignKey("collector_definitions.id"),nullable=False),
      sa.Column("enabled",sa.Boolean(),nullable=False),sa.Column("schedule_expression",sa.String(100),nullable=False),sa.Column("timeout_seconds",sa.Integer(),nullable=False),sa.Column("retry_count",sa.Integer(),nullable=False),
      sa.Column("config_version",sa.Integer(),nullable=False),sa.Column("configuration_json",sa.JSON(),nullable=False),sa.Column("created_by",sa.Integer(),sa.ForeignKey("users.id")),sa.Column("updated_by",sa.Integer(),sa.ForeignKey("users.id")),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.UniqueConstraint("target_id","collector_definition_id",name="uq_target_collector"))
    op.create_index("ix_collector_configs_target_id","collector_configs",["target_id"]); op.create_index("ix_collector_configs_collector_definition_id","collector_configs",["collector_definition_id"])
    op.create_table("collector_config_versions",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("collector_config_id",sa.Integer(),sa.ForeignKey("collector_configs.id",ondelete="CASCADE"),nullable=False),sa.Column("version",sa.Integer(),nullable=False),
      sa.Column("snapshot",sa.JSON(),nullable=False),sa.Column("changed_by",sa.Integer(),sa.ForeignKey("users.id")),sa.Column("change_reason",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()),
      sa.UniqueConstraint("collector_config_id","version",name="uq_collector_config_version"))
    op.create_index("ix_collector_config_versions_collector_config_id","collector_config_versions",["collector_config_id"])
    op.create_table("collector_runs",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("target_id",sa.Integer(),sa.ForeignKey("monitoring_targets.id",ondelete="CASCADE"),nullable=False),sa.Column("collector_config_id",sa.Integer(),sa.ForeignKey("collector_configs.id",ondelete="SET NULL")),
      sa.Column("collector_key",sa.String(100),nullable=False),sa.Column("config_version",sa.Integer()),sa.Column("status",run_enum,nullable=False),sa.Column("started_at",sa.DateTime(timezone=True)),sa.Column("completed_at",sa.DateTime(timezone=True)),
      sa.Column("duration_ms",sa.Integer()),sa.Column("records_collected",sa.Integer(),nullable=False),sa.Column("result_summary",sa.JSON(),nullable=False),sa.Column("error_message",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index("ix_collector_runs_target_id","collector_runs",["target_id"]); op.create_index("ix_collector_runs_collector_config_id","collector_runs",["collector_config_id"]); op.create_index("ix_collector_runs_collector_key","collector_runs",["collector_key"]); op.create_index("ix_collector_runs_status","collector_runs",["status"])

def downgrade():
    op.drop_table("collector_runs"); op.drop_table("collector_config_versions"); op.drop_table("collector_configs"); op.drop_table("collector_definitions"); op.drop_table("target_capabilities"); op.drop_table("monitoring_targets")
    run_enum.drop(op.get_bind(), checkfirst=True); capability_enum.drop(op.get_bind(), checkfirst=True)
