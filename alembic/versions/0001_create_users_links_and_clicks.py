"""create users, links and clicks

Revision ID: 0001
Revises:
Create Date: 2026-10-11 17:41:12.580550

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the users, links and clicks tables."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("target_url", sa.String(length=2048), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_links_owner_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_links")),
    )
    op.create_index(op.f("ix_links_code"), "links", ["code"], unique=True)
    op.create_index(op.f("ix_links_owner_id"), "links", ["owner_id"], unique=False)

    op.create_table(
        "clicks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("link_id", sa.Integer(), nullable=False),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_type", sa.String(length=10), nullable=False),
        sa.Column("referrer", sa.String(length=2048), nullable=True),
        sa.ForeignKeyConstraint(
            ["link_id"], ["links.id"], name=op.f("fk_clicks_link_id_links")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clicks")),
    )
    op.create_index(op.f("ix_clicks_link_id"), "clicks", ["link_id"], unique=False)


def downgrade() -> None:
    """Drop the tables again, in the reverse order."""
    op.drop_index(op.f("ix_clicks_link_id"), table_name="clicks")
    op.drop_table("clicks")

    op.drop_index(op.f("ix_links_owner_id"), table_name="links")
    op.drop_index(op.f("ix_links_code"), table_name="links")
    op.drop_table("links")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
