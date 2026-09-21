"""add image revisions

Revision ID: b71c9e4a2d10
Revises: 8f4d2c1a9b70
Create Date: 2026-10-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b71c9e4a2d10"
down_revision = "8f4d2c1a9b70"
branch_labels = None
depends_on = None

owner_kind = postgresql.ENUM(
    "WORLD", "CHARACTER", "NPC", "PLACE", name="image_owner_kind", create_type=False
)


def upgrade() -> None:
    owner_kind.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "image_revisions",
        sa.Column("world_id", sa.UUID(), nullable=False),
        sa.Column("owner_kind", owner_kind, nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("file_id", sa.UUID(), nullable=False),
        sa.Column("uploaded_by_id", sa.UUID(), nullable=True),
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
        sa.CheckConstraint(
            "owner_kind <> 'WORLD' OR owner_id = world_id",
            name=op.f("ck_image_revisions_world_owner_matches_world"),
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.id"],
            ondelete="CASCADE",
            name=op.f("fk_image_revisions_file_id_files"),
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["users.id"],
            ondelete="SET NULL",
            name=op.f("fk_image_revisions_uploaded_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["world_id"],
            ["worlds.id"],
            ondelete="CASCADE",
            name=op.f("fk_image_revisions_world_id_worlds"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_revisions")),
        sa.UniqueConstraint("file_id", name="uq_image_revisions_file_id"),
    )
    op.create_index(
        "ix_image_revisions_owner_history",
        "image_revisions",
        ["world_id", "owner_kind", "owner_id", "created_at"],
        unique=False,
    )

    for table, kind, uploader in (
        ("worlds", "WORLD", "created_by_id"),
        ("characters", "CHARACTER", "owner_id"),
        ("npcs", "NPC", "created_by_id"),
        ("places", "PLACE", "created_by_id"),
    ):
        world_expr = "id" if table == "worlds" else "world_id"
        op.execute(
            sa.text(
                f"""
                INSERT INTO image_revisions
                    (id, world_id, owner_kind, owner_id, file_id,
                     uploaded_by_id, created_at, updated_at)
                SELECT gen_random_uuid(), {world_expr}, '{kind}', id, image_file_id,
                       {uploader}, created_at, updated_at
                FROM {table}
                WHERE image_file_id IS NOT NULL
                """
            )
        )


def downgrade() -> None:
    op.drop_index("ix_image_revisions_owner_history", table_name="image_revisions")
    op.drop_table("image_revisions")
    owner_kind.drop(op.get_bind(), checkfirst=True)
