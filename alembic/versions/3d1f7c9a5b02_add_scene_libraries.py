"""scene libraries and reusable assets

Revision ID: 3d1f7c9a5b02
Revises: 5924a4c77999
Create Date: 2026-10-12 16:10:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "3d1f7c9a5b02"
down_revision = "5924a4c77999"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scene_libraries",
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("world_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
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
            name=op.f("fk_scene_libraries_created_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["world_id"],
            ["worlds.id"],
            ondelete="CASCADE",
            name=op.f("fk_scene_libraries_world_id_worlds"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scene_libraries")),
    )
    op.create_table(
        "scene_sections",
        sa.Column("library_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["library_id"],
            ["scene_libraries.id"],
            ondelete="CASCADE",
            name=op.f("fk_scene_sections_library_id_scene_libraries"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scene_sections")),
    )
    op.create_table(
        "scene_assets",
        sa.Column("section_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("fragment", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
            name=op.f("fk_scene_assets_created_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["scene_sections.id"],
            ondelete="CASCADE",
            name=op.f("fk_scene_assets_section_id_scene_sections"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scene_assets")),
    )


def downgrade() -> None:
    op.drop_table("scene_assets")
    op.drop_table("scene_sections")
    op.drop_table("scene_libraries")
