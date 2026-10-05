"""Worker presence separate from receiver/database availability."""
import sqlalchemy as sa
from alembic import op

revision = "005_worker_health"
down_revision = "004_shadow_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("service_pulses", sa.Column("name", sa.String(), primary_key=True),
                    sa.Column("seen_at", sa.Float(), nullable=False),
                    sa.Column("details", sa.JSON(), nullable=False))


def downgrade() -> None:
    op.drop_table("service_pulses")
