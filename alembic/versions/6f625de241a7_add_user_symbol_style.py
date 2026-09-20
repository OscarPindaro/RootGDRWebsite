"""add user symbol style

Revision ID: 6f625de241a7
Revises: 54fc49553c4e
Create Date: 2026-09-20 10:04:46.153145

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6f625de241a7"
down_revision = "54fc49553c4e"
branch_labels = None
depends_on = None

symbol_style = sa.Enum("ICONS", "SHAPES", name="symbol_style")


def upgrade() -> None:
    # Autogenerate does not emit CREATE TYPE for a new enum used in ADD COLUMN,
    # and NOT NULL needs a default for existing rows.
    symbol_style.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column(
            "symbol_style",
            symbol_style,
            nullable=False,
            server_default="ICONS",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "symbol_style")
    symbol_style.drop(op.get_bind(), checkfirst=True)
