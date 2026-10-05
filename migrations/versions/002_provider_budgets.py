"""Persist free-provider reservations across service restarts."""
import sqlalchemy as sa
from alembic import op

revision = "002_provider_budgets"
down_revision = "001_inbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("provider_state",
        sa.Column("provider", sa.String(), primary_key=True),
        sa.Column("cooldown_until", sa.Float(), nullable=False),
        sa.Column("last_status", sa.String(), nullable=True))
    op.create_table("provider_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False),
        sa.Column("actual_tokens", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False))
    op.create_index("ix_provider_usage_provider", "provider_usage", ["provider"])


def downgrade() -> None:
    op.drop_table("provider_usage")
    op.drop_table("provider_state")
