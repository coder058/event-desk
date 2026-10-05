"""Durable model/provider evidence distinct from the immutable submission payload."""
import sqlalchemy as sa
from alembic import op

revision = "003_analysis_trace"
down_revision = "002_provider_budgets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("analysis_trace", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "analysis_trace")

