from __future__ import annotations

import logging

from acp.schema import PromptResponse
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .acp.permissions import PermissionPolicyEngine
from .acp.process import AcpProcess, AcpProcessConfig, AcpProcessState
from .acp.runtime_client import RuntimeClient
from .config import AcpBotSettings
from .domain import PermissionPolicy, PromptRecord, QueueState, Verbosity
from .sessions import SessionCoordinator, SessionCoordinatorConfig
from .storage import StateDatabase, StateRepository
from .telegram import TelegramRenderer
from .telegram.permissions import TelegramPermissionBroker

logger = logging.getLogger(__name__)


class AcpTelegramApplication:
    def __init__(self, settings: AcpBotSettings, database: StateDatabase) -> None:
        self.settings = settings
        self.database = database
        self.state = StateRepository(database)
        self.renderer: TelegramRenderer | None = None
        self.permission_broker: TelegramPermissionBroker | None = None
        self.client = RuntimeClient(
            PermissionPolicyEngine(settings.devin_project_dir),
            self._policy_for_session,
            update_handler=self._handle_update,
            permission_handler=self._handle_permission,
        )
        self.process = AcpProcess(
            AcpProcessConfig(
                cwd=settings.devin_project_dir,
                executable=settings.devin_executable,
                arguments=("acp", "--model", settings.devin_default_model),
                startup_timeout=60,
            ),
            self.client,
        )
        self.coordinator = SessionCoordinator(
            SessionCoordinatorConfig(
                project_name=settings.devin_project_name,
                telegram_user_id=settings.telegram_allowed_user_id,
                default_verbosity=settings.devin_default_verbosity,
                default_policy=settings.devin_default_policy,
            ),
            self.state,
            self.process,
            on_started=self._turn_started,
            on_completed=self._turn_completed,
            on_failed=self._turn_failed,
        )

    def build(self) -> Application:
        application = (
            ApplicationBuilder()
            .token(self.settings.telegram_bot_token.get_secret_value())
            .post_init(self.startup)
            .post_shutdown(self.shutdown)
            .build()
        )
        authorized = (
            filters.User(user_id=self.settings.telegram_allowed_user_id)
            & filters.ChatType.PRIVATE
        )
        application.add_handler(CommandHandler("start", self.start, filters=authorized))
        application.add_handler(CommandHandler("help", self.start, filters=authorized))
        application.add_handler(CommandHandler("new", self.new, filters=authorized))
        application.add_handler(
            CommandHandler("status", self.status, filters=authorized)
        )
        application.add_handler(
            CommandHandler("cancel", self.cancel, filters=authorized)
        )
        application.add_handler(CommandHandler("force", self.force, filters=authorized))
        application.add_handler(CommandHandler("queue", self.queue, filters=authorized))
        application.add_handler(
            CommandHandler("verbosity", self.verbosity, filters=authorized)
        )
        application.add_handler(
            CommandHandler("policy", self.policy, filters=authorized)
        )
        application.add_handler(
            CallbackQueryHandler(self.permission_callback, pattern=r"^perm:")
        )
        application.add_handler(
            CallbackQueryHandler(self.policy_callback, pattern=r"^policy:")
        )
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND & authorized, self.prompt)
        )
        return application

    async def startup(self, application: Application) -> None:
        self.renderer = TelegramRenderer(
            application.bot,
            self.settings.telegram_allowed_user_id,
            self.settings.devin_default_verbosity,
            self.settings.devin_render_debounce_seconds,
            self.settings.devin_max_image_bytes,
        )
        self.permission_broker = TelegramPermissionBroker(
            application.bot,
            self.settings.telegram_allowed_user_id,
            self.settings.telegram_allowed_user_id,
            self.state,
        )
        await application.bot.set_my_commands(
            [
                BotCommand("new", "Start a new ACP session"),
                BotCommand("status", "Show session state"),
                BotCommand("queue", "Show or resume queued prompts"),
                BotCommand("verbosity", "Set session verbosity"),
                BotCommand("policy", "Set permission policy"),
                BotCommand("cancel", "Cancel the active turn"),
            ]
        )
        session = await self.coordinator.start()
        self.renderer.verbosity = session.verbosity
        if self.coordinator.queue_paused:
            await application.bot.send_message(
                self.settings.telegram_allowed_user_id,
                "Recovered queued work is paused. Use /queue resume to continue.",
            )

    async def shutdown(self, application: Application) -> None:
        if self.renderer is not None:
            await self.renderer.close()
        await self.coordinator.stop()
        await self.database.close()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(
            update,
            "/new /status /queue /force /verbosity /policy /cancel",
        )

    async def prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None or not message.text:
            return
        queued = await self.coordinator.submit(message.text.strip())
        if self.coordinator.queue_paused:
            await message.reply_text(
                f"Prompt queued as #{queued.id}. Use /queue resume to continue."
            )
        elif self.process.state == AcpProcessState.RUNNING:
            await message.reply_text(f"Prompt queued as #{queued.id}.")

    async def new(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.process.state == AcpProcessState.RUNNING:
            await self._reply(
                update, "Cancel the active turn before creating a session."
            )
            return
        session = await self.coordinator.new_session()
        if self.renderer is not None:
            self.renderer.verbosity = session.verbosity
        await self._reply(update, f"New ACP session: {session.acp_session_id}")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        session = self.coordinator.active_session
        if session is None:
            await self._reply(update, "No active ACP session.")
            return
        queued = await self.state.list_prompts(session.id, {QueueState.QUEUED})
        await self._reply(
            update,
            "\n".join(
                [
                    f"Session: {session.acp_session_id}",
                    f"Agent: {self.process.state}",
                    f"Verbosity: {session.verbosity}",
                    f"Policy: {session.policy}",
                    f"Queued: {len(queued)}",
                ]
            ),
        )

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        session = self.coordinator.active_session
        if session is None or self.process.state != AcpProcessState.RUNNING:
            await self._reply(update, "No active turn.")
            return
        if self.permission_broker is not None:
            await self.permission_broker.cancel_session(session.acp_session_id)
        await self.process.cancel(session.acp_session_id)
        await self._reply(update, "Cancellation requested.")

    async def force(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        prompt = " ".join(context.args).strip()
        if not prompt:
            await self._reply(update, "Usage: /force <prompt>")
            return
        queued = await self.coordinator.force(prompt)
        await self._reply(update, f"Forced prompt queued as #{queued.id}.")

    async def queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if context.args == ["resume"]:
            self.coordinator.resume_queue()
            await self._reply(update, "Queue resumed.")
            return
        session = self.coordinator.active_session
        if session is None:
            await self._reply(update, "No active session.")
            return
        items = await self.state.list_prompts(
            session.id,
            {QueueState.QUEUED, QueueState.INTERRUPTED},
        )
        text = "\n".join(f"#{item.id} [{item.state}]" for item in items)
        await self._reply(update, text or "Queue is empty.")

    async def verbosity(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        session = self.coordinator.active_session
        if session is None:
            await self._reply(update, "No active session.")
            return
        if len(context.args) != 1:
            await self._reply(update, "Usage: /verbosity quiet|status|verbose|trace")
            return
        try:
            selected = Verbosity(context.args[0])
        except ValueError:
            await self._reply(update, "Unknown verbosity.")
            return
        updated = await self.state.set_session_preferences(
            session.id, verbosity=selected
        )
        self.coordinator.active_session = updated
        if self.renderer is not None:
            self.renderer.verbosity = selected
        await self._reply(update, f"Verbosity: {selected}")

    async def policy(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if context.args == ["balanced"]:
            await self._set_policy(PermissionPolicy.BALANCED)
            await self._reply(update, "Permission policy: balanced")
            return
        if context.args == ["bypass"]:
            await self._reply(
                update,
                "Bypass auto-approves actions inside the workspace. Confirm?",
                InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Enable bypass", callback_data="policy:bypass"
                            ),
                            InlineKeyboardButton(
                                "Cancel", callback_data="policy:cancel"
                            ),
                        ]
                    ]
                ),
            )
            return
        await self._reply(update, "Usage: /policy balanced|bypass")

    async def policy_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        if (
            query is None
            or query.from_user.id != self.settings.telegram_allowed_user_id
        ):
            return
        if query.data == "policy:bypass":
            await self._set_policy(PermissionPolicy.BYPASS)
            await query.answer("Bypass enabled")
            await query.edit_message_text("Permission policy: bypass")
        else:
            await query.answer("Cancelled")
            await query.edit_message_text("Permission policy unchanged")

    async def permission_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if self.permission_broker is not None:
            await self.permission_broker.handle_callback(update)

    async def _turn_started(self, prompt: PromptRecord) -> None:
        if self.renderer is None:
            return
        self.renderer.begin_turn()
        if self.renderer.verbosity != Verbosity.QUIET:
            await self.renderer.bot.send_message(
                self.settings.telegram_allowed_user_id,
                f"Devin started prompt #{prompt.id}.",
            )

    async def _turn_completed(
        self, prompt: PromptRecord, result: PromptResponse
    ) -> None:
        if self.renderer is not None:
            await self.renderer.finish_turn(result.stop_reason)

    async def _turn_failed(self, prompt: PromptRecord, error: Exception) -> None:
        logger.error("ACP turn failed: %s", type(error).__name__)
        if self.renderer is not None:
            await self.renderer.bot.send_message(
                self.settings.telegram_allowed_user_id,
                f"Prompt #{prompt.id} failed. Use /queue to inspect recovery state.",
            )

    async def _handle_update(self, session_id: str, update) -> None:
        if self.renderer is not None:
            await self.renderer.on_update(session_id, update)

    async def _handle_permission(self, session_id, tool_call, options):
        if self.permission_broker is None:
            return None
        return await self.permission_broker.request(session_id, tool_call, options)

    def _policy_for_session(self, session_id: str) -> PermissionPolicy:
        session = self.coordinator.active_session
        if session is None or session.acp_session_id != session_id:
            return PermissionPolicy.BALANCED
        return session.policy

    async def _set_policy(self, policy: PermissionPolicy) -> None:
        session = self.coordinator.active_session
        if session is None:
            raise RuntimeError("No active session")
        updated = await self.state.set_session_preferences(session.id, policy=policy)
        await self.state.set_default_policy(
            self.settings.telegram_allowed_user_id, policy
        )
        self.coordinator.active_session = updated

    async def _reply(
        self,
        update: Update,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        message = update.effective_message
        if message is not None:
            await message.reply_text(text, reply_markup=reply_markup)
