"""Immutable one-time research quota ledger import identity."""
import sqlalchemy as sa
from alembic import op

revision = "010_quota_imports"
down_revision = "009_source_checkpoints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("quota_imports", sa.Column("ledger_id", sa.String(), primary_key=True),
        sa.Column("snapshot_sha256", sa.String(), nullable=False),
        sa.Column("captured_at", sa.Float(), nullable=False),
        sa.Column("imported_at", sa.Float(), nullable=False),
        sa.Column("usage_rows", sa.Integer(), nullable=False))


def downgrade() -> None:
    op.drop_table("quota_imports")
