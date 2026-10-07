"""Shared durable identified SEC pacing clock and request metadata."""
import sqlalchemy as sa
from alembic import op

revision = "011_sec_http_gate"
down_revision = "010_quota_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("sec_http_budget", sa.Column("name", sa.String(), primary_key=True),
                    sa.Column("not_before", sa.Float(), nullable=False))
    op.create_table("sec_http_reads", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_url", sa.String(), nullable=False), sa.Column("started_at", sa.Float(), nullable=False),
        sa.Column("completed_at", sa.Float(), nullable=True), sa.Column("state", sa.String(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True), sa.Column("content_bytes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_table("sec_http_reads")
    op.drop_table("sec_http_budget")
