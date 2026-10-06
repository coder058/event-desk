"""Append-only official counter snapshots and deduplicated calendar versions."""
import sqlalchemy as sa
from alembic import op

revision = "008_competition_observations"
down_revision = "007_configuration_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("competition_calendars", sa.Column("content_hash", sa.String(), primary_key=True),
                    sa.Column("events", sa.JSON(), nullable=False))
    op.create_table("competition_observations", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slot", sa.String(), nullable=False), sa.Column("started_at", sa.Float(), nullable=False),
        sa.Column("observed_at", sa.Float(), nullable=False),
        sa.Column("calendar_hash", sa.String(), sa.ForeignKey("competition_calendars.content_hash"), nullable=False),
        sa.Column("calendar_raw_hash", sa.String(), nullable=False),
        sa.Column("health_raw_hash", sa.String(), nullable=False),
        sa.Column("health", sa.JSON(), nullable=False), sa.Column("summary", sa.JSON(), nullable=False))
    op.create_index("ix_competition_observations_slot", "competition_observations", ["slot"])


def downgrade() -> None:
    op.drop_table("competition_observations")
    op.drop_table("competition_calendars")
