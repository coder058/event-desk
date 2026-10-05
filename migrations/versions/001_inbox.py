"""Initial durable inbox and prediction outbox."""
import sqlalchemy as sa
from alembic import op

revision = "001_inbox"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slot", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("event", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.Float(), nullable=False),
        sa.Column("deadline", sa.Float(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("lease_until", sa.Float(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("inputs", sa.JSON(), nullable=True),
        sa.Column("inputs_hash", sa.String(), nullable=True),
        sa.Column("model_hash", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("fallback", sa.String(), nullable=True),
        sa.Column("response", sa.JSON(), nullable=True),
        sa.Column("submitted_at", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint("slot", "event_id"))
    op.create_table("deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slot", sa.String(), nullable=False),
        sa.Column("webhook_id", sa.String(), nullable=False),
        sa.Column("body_hash", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("received_at", sa.Float(), nullable=False),
        sa.UniqueConstraint("slot", "webhook_id"))


def downgrade() -> None:
    op.drop_table("deliveries")
    op.drop_table("jobs")
