"""add world invites

Revision ID: c35a50fec1ae
Revises: b71c9e4a2d10
Create Date: 2026-09-21 20:29:51.889627

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c35a50fec1ae"
down_revision = "b71c9e4a2d10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "world_invites",
        sa.Column("world_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("MASTER", "PLAYER", name="world_role", create_type=False),
            nullable=False,
        ),
        sa.Column("invited_by", sa.UUID(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
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
        sa.ForeignKeyConstraint(
            ["invited_by"], ["users.id"], name=op.f("fk_world_invites_invited_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["world_id"],
            ["worlds.id"],
            name=op.f("fk_world_invites_world_id_worlds"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_world_invites")),
        sa.UniqueConstraint("world_id", "email", name="uq_world_invite_email"),
    )


def downgrade() -> None:
    op.drop_table("world_invites")
