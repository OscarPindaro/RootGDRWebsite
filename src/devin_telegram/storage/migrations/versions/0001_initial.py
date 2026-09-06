from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devin_telegram_projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("root_path", sa.String(2048), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "devin_telegram_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("acp_session_id", sa.String(255), nullable=False),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("devin_telegram_projects.id"),
            nullable=False,
        ),
        sa.Column("telegram_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column(
            "state",
            sa.Enum(
                "idle",
                "running",
                "requires_action",
                "interrupted",
                "closed",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "verbosity",
            sa.Enum("quiet", "status", "verbose", "trace", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "policy",
            sa.Enum("balanced", "bypass", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("acp_session_id", name="uq_devin_telegram_session_acp"),
    )
    op.create_index(
        "ix_devin_telegram_sessions_project_id",
        "devin_telegram_sessions",
        ["project_id"],
    )
    op.create_index(
        "ix_devin_telegram_sessions_telegram_user_id",
        "devin_telegram_sessions",
        ["telegram_user_id"],
    )
    op.create_table(
        "devin_telegram_user_preferences",
        sa.Column("telegram_user_id", sa.Integer(), primary_key=True),
        sa.Column(
            "default_project_id",
            sa.Integer(),
            sa.ForeignKey("devin_telegram_projects.id"),
            nullable=False,
        ),
        sa.Column(
            "active_session_id",
            sa.Integer(),
            sa.ForeignKey("devin_telegram_sessions.id"),
        ),
        sa.Column(
            "default_verbosity",
            sa.Enum("quiet", "status", "verbose", "trace", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "default_policy",
            sa.Enum("balanced", "bypass", native_enum=False),
            nullable=False,
        ),
    )
    op.create_table(
        "devin_telegram_prompt_queue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("devin_telegram_sessions.id"),
            nullable=False,
        ),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("attachment_manifest", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "queued",
                "dispatching",
                "accepted",
                "completed",
                "cancelled",
                "interrupted",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_devin_telegram_prompt_queue_session_id",
        "devin_telegram_prompt_queue",
        ["session_id"],
    )
    op.create_table(
        "devin_telegram_pending_permissions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("devin_telegram_sessions.id"),
            nullable=False,
        ),
        sa.Column("tool_call_id", sa.String(255), nullable=False),
        sa.Column("options", sa.Text(), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("telegram_message_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_devin_telegram_pending_permissions_session_id",
        "devin_telegram_pending_permissions",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_devin_telegram_pending_permissions_session_id",
        table_name="devin_telegram_pending_permissions",
    )
    op.drop_table("devin_telegram_pending_permissions")
    op.drop_index(
        "ix_devin_telegram_prompt_queue_session_id",
        table_name="devin_telegram_prompt_queue",
    )
    op.drop_table("devin_telegram_prompt_queue")
    op.drop_table("devin_telegram_user_preferences")
    op.drop_index(
        "ix_devin_telegram_sessions_telegram_user_id",
        table_name="devin_telegram_sessions",
    )
    op.drop_index(
        "ix_devin_telegram_sessions_project_id",
        table_name="devin_telegram_sessions",
    )
    op.drop_table("devin_telegram_sessions")
    op.drop_table("devin_telegram_projects")
