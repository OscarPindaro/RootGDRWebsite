"""add world images

Revision ID: f2e84d6a1c09
Revises: a9f31b7c2d4e
Create Date: 2026-09-05

"""

import sqlalchemy as sa
from alembic import op

revision = "f2e84d6a1c09"
down_revision = "a9f31b7c2d4e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("worlds", sa.Column("image_file_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_worlds_image_file_id_files",
        "worlds",
        "files",
        ["image_file_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_worlds_image_file_id_files", "worlds", type_="foreignkey")
    op.drop_column("worlds", "image_file_id")
