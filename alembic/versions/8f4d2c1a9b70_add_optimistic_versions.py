"""add optimistic versions

Revision ID: 8f4d2c1a9b70
Revises: 6f625de241a7
Create Date: 2026-10-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "8f4d2c1a9b70"
down_revision = "6f625de241a7"
branch_labels = None
depends_on = None

_TABLES = ("worlds", "characters", "npcs", "places", "sessions", "stories", "pages")


def upgrade() -> None:
    for table_name in _TABLES:
        op.add_column(table_name, sa.Column("version", sa.Integer(), nullable=True))
        op.execute(sa.text(f'UPDATE "{table_name}" SET version = 1'))
        op.alter_column(
            table_name,
            "version",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade() -> None:
    for table_name in reversed(_TABLES):
        op.drop_column(table_name, "version")
