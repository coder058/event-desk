"""Raw-source provenance and atomic append-only batch/checkpoint ledger."""
import sqlalchemy as sa
from alembic import op

revision = "009_source_checkpoints"
down_revision = "008_competition_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("source_captures", sa.Column("manifest_hash", sa.String(), primary_key=True),
        sa.Column("source", sa.String(), nullable=False), sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("first_seen_at", sa.Float(), nullable=False), sa.Column("accepted_at", sa.Float(), nullable=True),
        sa.Column("provenance", sa.JSON(), nullable=False))
    op.create_index("ix_source_captures_source", "source_captures", ["source"])
    op.create_index("ix_source_captures_content_hash", "source_captures", ["content_hash"])
    op.create_table("source_batches", sa.Column("manifest_hash", sa.String(), primary_key=True),
        sa.Column("feed_key", sa.String(), nullable=False), sa.Column("completed_at", sa.Float(), nullable=False),
        sa.Column("previous_head", sa.String(), sa.ForeignKey("source_batches.manifest_hash"), nullable=True),
        sa.Column("checkpoint", sa.JSON(), nullable=False), sa.Column("capture_hashes", sa.JSON(), nullable=False))
    op.create_index("ix_source_batches_feed_key", "source_batches", ["feed_key"])
    op.create_table("source_cursors", sa.Column("feed_key", sa.String(), primary_key=True),
        sa.Column("head", sa.String(), sa.ForeignKey("source_batches.manifest_hash"), nullable=False))


def downgrade() -> None:
    op.drop_table("source_cursors")
    op.drop_table("source_batches")
    op.drop_table("source_captures")
