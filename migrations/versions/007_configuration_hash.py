"""Retain the specific frozen configuration with each immutable prediction."""
import sqlalchemy as sa
from alembic import op

revision = "007_configuration_hash"
down_revision = "006_local_trace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("configuration_hash", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "configuration_hash")
