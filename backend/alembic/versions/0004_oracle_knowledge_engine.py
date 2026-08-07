"""oracle knowledge catalog and digital twin"""
from alembic import op
import sqlalchemy as sa

revision = "0004_oracle_knowledge_engine"
down_revision = "0003_metric_pipeline"
branch_labels = None
depends_on = None

resource_type = sa.Enum("DICTIONARY_VIEW", "PACKAGE", "PACKAGE_MEMBER", name="knowledgeresourcetype")
change_type = sa.Enum(
    "DISCOVERED", "REMOVED", "STATUS_CHANGED", "DDL_CHANGED", "STATS_EPOCH_CHANGED",
    "STALE_STATS_CHANGED", "ROW_ESTIMATE_CHANGED", "MODIFICATIONS_CHANGED",
    "PARTITION_COUNT_CHANGED", "INDEX_STATUS_CHANGED", name="changetype"
)


def upgrade():
    resource_type.create(op.get_bind(), checkfirst=True)
    change_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "oracle_knowledge_resources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target_id", sa.Integer(), sa.ForeignKey("monitoring_targets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", resource_type, nullable=False),
        sa.Column("resource_name", sa.String(256), nullable=False),
        sa.Column("owner_name", sa.String(128)),
        sa.Column("domain", sa.String(80), nullable=False),
        sa.Column("privilege_tier", sa.Integer(), nullable=False),
        sa.Column("accessible", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("target_id", "resource_type", "resource_name", name="uq_oracle_knowledge_resource"),
    )
    for col in ["target_id", "resource_type", "resource_name", "owner_name", "domain", "privilege_tier", "accessible", "last_seen_at"]:
        op.create_index(f"ix_oracle_knowledge_resources_{col}", "oracle_knowledge_resources", [col])

    op.create_table(
        "digital_twin_objects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target_id", sa.Integer(), sa.ForeignKey("monitoring_targets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("owner_name", sa.String(128), nullable=False),
        sa.Column("object_name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(40)),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("target_id", "object_type", "owner_name", "object_name", name="uq_twin_object"),
    )
    for col in ["target_id", "object_type", "owner_name", "object_name", "status", "fingerprint", "last_seen_at", "changed_at"]:
        op.create_index(f"ix_digital_twin_objects_{col}", "digital_twin_objects", [col])

    op.create_table(
        "metadata_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target_id", sa.Integer(), sa.ForeignKey("monitoring_targets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("twin_object_id", sa.Integer(), sa.ForeignKey("digital_twin_objects.id", ondelete="SET NULL")),
        sa.Column("change_type", change_type, nullable=False),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("owner_name", sa.String(128), nullable=False),
        sa.Column("object_name", sa.String(128), nullable=False),
        sa.Column("before_json", sa.JSON()),
        sa.Column("after_json", sa.JSON()),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for col in ["target_id", "twin_object_id", "change_type", "object_type", "owner_name", "object_name", "detected_at"]:
        op.create_index(f"ix_metadata_changes_{col}", "metadata_changes", [col])


def downgrade():
    op.drop_table("metadata_changes")
    op.drop_table("digital_twin_objects")
    op.drop_table("oracle_knowledge_resources")
    change_type.drop(op.get_bind(), checkfirst=True)
    resource_type.drop(op.get_bind(), checkfirst=True)
