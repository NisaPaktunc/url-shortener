"""add click index for statistics

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11 17:52:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Index clicks by link and time. The old link-only index is not needed anymore."""
    op.create_index(
        "ix_clicks_link_id_clicked_at",
        "clicks",
        ["link_id", "clicked_at"],
        unique=False,
    )
    op.drop_index(op.f("ix_clicks_link_id"), table_name="clicks")


def downgrade() -> None:
    """Go back to the index on link_id only."""
    op.create_index(op.f("ix_clicks_link_id"), "clicks", ["link_id"], unique=False)
    op.drop_index("ix_clicks_link_id_clicked_at", table_name="clicks")
