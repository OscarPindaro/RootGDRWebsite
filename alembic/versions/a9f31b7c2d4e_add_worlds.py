"""add worlds

Revision ID: a9f31b7c2d4e
Revises: 8c295a24627a
Create Date: 2026-09-05

"""

import sqlalchemy as sa
from alembic import op

revision = "a9f31b7c2d4e"
down_revision = "8c295a24627a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worlds",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "world_shared_users",
        sa.Column("world_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("world_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("world_shared_users")
    op.drop_table("worlds")
