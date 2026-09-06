from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from acp.schema import PermissionOption
from sqlalchemy import select, update

from ..domain import (
    AttachmentManifest,
    PendingPermissionRecord,
    PermissionOptions,
    PermissionPolicy,
    ProjectRecord,
    PromptRecord,
    QueueState,
    SessionRecord,
    SessionState,
    UserPreferencesRecord,
    Verbosity,
)
from .database import StateDatabase
from .models import (
    PendingPermissionModel,
    ProjectModel,
    PromptModel,
    SessionModel,
    UserPreferencesModel,
)
from .schemas import (
    PendingPermissionCreate,
    ProjectCreate,
    PromptCreate,
    SessionCreate,
    UserPreferencesCreate,
)


class StateRepository:
    def __init__(self, database: StateDatabase) -> None:
        self.database = database

    async def add_project(self, data: ProjectCreate) -> ProjectRecord:
        root = data.root_path.expanduser().resolve()
        async with self.database.sessions.begin() as session:
            model = await session.scalar(
                select(ProjectModel).where(ProjectModel.name == data.name)
            )
            if model is None:
                model = ProjectModel(name=data.name, root_path=str(root))
                session.add(model)
                await session.flush()
            else:
                model.root_path = str(root)
        if model is None:
            raise RuntimeError("Project upsert failed")
        return ProjectRecord.model_validate(model)

    async def ensure_user(self, data: UserPreferencesCreate) -> None:
        async with self.database.sessions.begin() as session:
            model = await session.get(UserPreferencesModel, data.telegram_user_id)
            if model is None:
                session.add(
                    UserPreferencesModel(
                        telegram_user_id=data.telegram_user_id,
                        default_project_id=data.default_project_id,
                        default_verbosity=data.default_verbosity,
                        default_policy=data.default_policy,
                    )
                )

    async def get_user_preferences(
        self, telegram_user_id: int
    ) -> UserPreferencesRecord:
        async with self.database.sessions() as session:
            model = await session.get(UserPreferencesModel, telegram_user_id)
        if model is None:
            raise KeyError(telegram_user_id)
        return UserPreferencesRecord.model_validate(model)

    async def set_default_policy(
        self, telegram_user_id: int, policy: PermissionPolicy
    ) -> None:
        async with self.database.sessions.begin() as session:
            await session.execute(
                update(UserPreferencesModel)
                .where(UserPreferencesModel.telegram_user_id == telegram_user_id)
                .values(default_policy=policy)
            )

    async def create_session(self, data: SessionCreate) -> SessionRecord:
        async with self.database.sessions.begin() as session:
            model = SessionModel(
                acp_session_id=data.acp_session_id,
                project_id=data.project_id,
                telegram_user_id=data.telegram_user_id,
                state=data.state,
                verbosity=data.verbosity,
                policy=data.policy,
            )
            session.add(model)
            await session.flush()
            await session.execute(
                update(UserPreferencesModel)
                .where(UserPreferencesModel.telegram_user_id == data.telegram_user_id)
                .values(
                    active_session_id=model.id,
                    default_project_id=data.project_id,
                )
            )
        return SessionRecord.model_validate(model)

    async def get_session(self, session_id: int) -> SessionRecord:
        async with self.database.sessions() as session:
            model = await session.get(SessionModel, session_id)
        if model is None:
            raise KeyError(session_id)
        return SessionRecord.model_validate(model)

    async def get_session_by_acp(self, acp_session_id: str) -> SessionRecord:
        async with self.database.sessions() as session:
            model = await session.scalar(
                select(SessionModel).where(
                    SessionModel.acp_session_id == acp_session_id
                )
            )
        if model is None:
            raise KeyError(acp_session_id)
        return SessionRecord.model_validate(model)

    async def get_active_session(self, telegram_user_id: int) -> SessionRecord | None:
        async with self.database.sessions() as session:
            preferences = await session.get(UserPreferencesModel, telegram_user_id)
            if preferences is None or preferences.active_session_id is None:
                return None
            model = await session.get(SessionModel, preferences.active_session_id)
        return SessionRecord.model_validate(model) if model else None

    async def list_sessions(
        self, telegram_user_id: int, project_id: int
    ) -> list[SessionRecord]:
        async with self.database.sessions() as session:
            models = list(
                await session.scalars(
                    select(SessionModel)
                    .where(
                        SessionModel.telegram_user_id == telegram_user_id,
                        SessionModel.project_id == project_id,
                    )
                    .order_by(SessionModel.updated_at.desc(), SessionModel.id.desc())
                )
            )
        return [SessionRecord.model_validate(model) for model in models]

    async def set_active_session(self, telegram_user_id: int, session_id: int) -> None:
        async with self.database.sessions.begin() as session:
            await session.execute(
                update(UserPreferencesModel)
                .where(UserPreferencesModel.telegram_user_id == telegram_user_id)
                .values(active_session_id=session_id)
            )

    async def set_session_state(
        self, session_id: int, state: SessionState, title: str | None = None
    ) -> None:
        async with self.database.sessions.begin() as session:
            model = await session.get(SessionModel, session_id)
            if model is None:
                raise KeyError(session_id)
            model.state = state
            model.updated_at = datetime.now(timezone.utc)
            if title is not None:
                model.title = title

    async def set_session_preferences(
        self,
        session_id: int,
        verbosity: Verbosity | None = None,
        policy: PermissionPolicy | None = None,
    ) -> SessionRecord:
        current = await self.get_session(session_id)
        async with self.database.sessions.begin() as session:
            await session.execute(
                update(SessionModel)
                .where(SessionModel.id == session_id)
                .values(
                    verbosity=verbosity or current.verbosity,
                    policy=policy or current.policy,
                    updated_at=datetime.now(timezone.utc),
                )
            )
        return await self.get_session(session_id)

    async def enqueue_prompt(self, data: PromptCreate) -> PromptRecord:
        async with self.database.sessions.begin() as session:
            model = PromptModel(
                session_id=data.session_id,
                prompt_text=data.prompt_text,
                attachment_manifest=data.attachment_manifest,
                priority=data.priority,
                state=data.state,
            )
            session.add(model)
            await session.flush()
        return PromptRecord.model_validate(model)

    async def get_prompt(self, prompt_id: int) -> PromptRecord:
        async with self.database.sessions() as session:
            model = await session.get(PromptModel, prompt_id)
        if model is None:
            raise KeyError(prompt_id)
        return PromptRecord.model_validate(model)

    async def next_prompt(self, session_id: int) -> PromptRecord | None:
        async with self.database.sessions() as session:
            model = await session.scalar(
                select(PromptModel)
                .where(
                    PromptModel.session_id == session_id,
                    PromptModel.state == QueueState.QUEUED,
                )
                .order_by(PromptModel.priority.desc(), PromptModel.id)
                .limit(1)
            )
        return PromptRecord.model_validate(model) if model else None

    async def list_prompts(
        self, session_id: int, states: set[QueueState] | None = None
    ) -> list[PromptRecord]:
        statement = select(PromptModel).where(PromptModel.session_id == session_id)
        if states:
            statement = statement.where(PromptModel.state.in_(states))
        statement = statement.order_by(PromptModel.priority.desc(), PromptModel.id)
        async with self.database.sessions() as session:
            models = list(await session.scalars(statement))
        return [PromptRecord.model_validate(model) for model in models]

    async def set_prompt_state(self, prompt_id: int, state: QueueState) -> None:
        async with self.database.sessions.begin() as session:
            model = await session.get(PromptModel, prompt_id)
            if model is None:
                raise KeyError(prompt_id)
            model.state = state
            if state in {QueueState.DISPATCHING, QueueState.ACCEPTED}:
                model.dispatched_at = datetime.now(timezone.utc)

    async def create_pending_permission(
        self, data: PendingPermissionCreate
    ) -> PendingPermissionRecord:
        async with self.database.sessions.begin() as session:
            model = PendingPermissionModel(
                id=data.id,
                session_id=data.session_id,
                tool_call_id=data.tool_call_id,
                options=PermissionOptions(items=data.options),
            )
            session.add(model)
        return PendingPermissionRecord.model_validate(model)

    async def get_pending_permission(
        self, permission_id: str
    ) -> PendingPermissionRecord:
        async with self.database.sessions() as session:
            model = await session.get(PendingPermissionModel, permission_id)
        if model is None:
            raise KeyError(permission_id)
        return PendingPermissionRecord.model_validate(model)

    async def set_permission_message(self, permission_id: str, message_id: int) -> None:
        async with self.database.sessions.begin() as session:
            await session.execute(
                update(PendingPermissionModel)
                .where(
                    PendingPermissionModel.id == permission_id,
                    PendingPermissionModel.state == "pending",
                )
                .values(telegram_message_id=message_id)
            )

    async def resolve_permission(self, permission_id: str, state: str) -> bool:
        async with self.database.sessions.begin() as session:
            result = await session.execute(
                update(PendingPermissionModel)
                .where(
                    PendingPermissionModel.id == permission_id,
                    PendingPermissionModel.state == "pending",
                )
                .values(state=state, resolved_at=datetime.now(timezone.utc))
            )
        return result.rowcount == 1

    async def recover_interrupted(self) -> tuple[int, int]:
        async with self.database.sessions.begin() as session:
            prompt_result = await session.execute(
                update(PromptModel)
                .where(
                    PromptModel.state.in_({QueueState.DISPATCHING, QueueState.ACCEPTED})
                )
                .values(state=QueueState.INTERRUPTED)
            )
            session_result = await session.execute(
                update(SessionModel)
                .where(
                    SessionModel.state.in_(
                        {SessionState.RUNNING, SessionState.REQUIRES_ACTION}
                    )
                )
                .values(
                    state=SessionState.INTERRUPTED,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.execute(
                update(PendingPermissionModel)
                .where(PendingPermissionModel.state == "pending")
                .values(state="stale", resolved_at=datetime.now(timezone.utc))
            )
        return prompt_result.rowcount, session_result.rowcount
