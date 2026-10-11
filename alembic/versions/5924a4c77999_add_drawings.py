"""add drawings

Revision ID: 5924a4c77999
Revises: c35a50fec1ae
Create Date: 2026-10-11 01:19:57.784918

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "5924a4c77999"
down_revision = "c35a50fec1ae"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "drawings",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            ondelete="SET NULL",
            name=op.f("fk_drawings_created_by_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_drawings")),
    )


def downgrade() -> None:
    op.drop_table("drawings")
