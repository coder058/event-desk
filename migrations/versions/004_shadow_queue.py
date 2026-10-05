"""Separate best-effort evidence from deadline-critical predictions."""
import sqlalchemy as sa
from alembic import op

revision = "004_shadow_queue"
down_revision = "003_analysis_trace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("shadow_state", sa.String(), nullable=True))
    # SOURCE: zero means no held lease, matching the existing inbox convention.
    op.add_column("jobs", sa.Column("shadow_lease_until", sa.Float(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("jobs", "shadow_lease_until")
    op.drop_column("jobs", "shadow_state")
