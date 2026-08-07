"""phase 1 foundation"""
from alembic import op
import sqlalchemy as sa
revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None
role_enum = sa.Enum("ADMIN", "OPERATOR", "VIEWER", name="role")
def upgrade():
    role_enum.create(op.get_bind(), checkfirst=True)
    op.create_table("users",
      sa.Column("id", sa.Integer(), primary_key=True),
      sa.Column("username", sa.String(100), nullable=False),
      sa.Column("email", sa.String(255), nullable=False),
      sa.Column("password_hash", sa.String(255), nullable=False),
      sa.Column("role", role_enum, nullable=False),
      sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
      sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("platform_settings",
      sa.Column("id", sa.Integer(), primary_key=True),
      sa.Column("key", sa.String(150), nullable=False, unique=True),
      sa.Column("value", sa.JSON(), nullable=False),
      sa.Column("description", sa.Text()),
      sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id")),
      sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("audit_events",
      sa.Column("id", sa.Integer(), primary_key=True),
      sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id")),
      sa.Column("action", sa.String(100), nullable=False),
      sa.Column("entity_type", sa.String(100), nullable=False),
      sa.Column("entity_id", sa.String(100)),
      sa.Column("before_data", sa.JSON()),
      sa.Column("after_data", sa.JSON()),
      sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    from app.core.security import hash_password
    users = sa.table("users", sa.column("username"), sa.column("email"), sa.column("password_hash"), sa.column("role"), sa.column("is_active"))
    op.bulk_insert(users, [{"username":"admin","email":"admin@local","password_hash":hash_password("Admin123!"),"role":"ADMIN","is_active":True}])
    settings = sa.table("platform_settings", sa.column("key"), sa.column("value"), sa.column("description"))
    op.bulk_insert(settings, [
      {"key":"retention.defaults","value":{"metrics_days":365,"audit_days":730},"description":"Default platform retention"},
      {"key":"ui.branding","value":{"product_name":"Oracle Operational Intelligence","theme":"light"},"description":"Portal branding"}
    ])
def downgrade():
    op.drop_table("audit_events")
    op.drop_table("platform_settings")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
    role_enum.drop(op.get_bind(), checkfirst=True)
