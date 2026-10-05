"""Freeze actual local model computations with the submitted prediction."""
import sqlalchemy as sa
from alembic import op

revision = "006_local_trace"
down_revision = "005_worker_health"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("local_trace", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "local_trace")
