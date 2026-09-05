from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from telegram import Bot, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)
_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_FAMILIES_PER_PAGE = 8
_VARIANTS_PER_PAGE = 8


def _devin_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("TELEGRAM_")
    }


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: SecretStr
    telegram_allowed_user_id: int
    devin_project_dir: Path
    devin_executable: str = "devin"
    devin_sandbox: bool = True
    devin_permission_mode: Literal["auto", "accept-edits", "smart", "dangerous"] = (
        "auto"
    )
    devin_models: str = "adaptive,gpt,opus,swe"
    devin_default_model: str = "adaptive"

    @field_validator("devin_project_dir")
    @classmethod
    def validate_project_dir(cls, value: Path) -> Path:
        path = value.expanduser()
        if not path.is_dir():
            raise ValueError("must be an existing directory")
        return path.resolve()

    @field_validator("devin_executable")
    @classmethod
    def validate_executable(cls, value: str) -> str:
        if not value or shutil.which(value) is None:
            raise ValueError("must resolve to an executable")
        return value

    @field_validator("devin_models")
    @classmethod
    def validate_models(cls, value: str) -> str:
        models = [model.strip() for model in value.split(",") if model.strip()]
        if not models:
            raise ValueError("must contain at least one model")
        if any(
            len(model) > 50 or not _MODEL_PATTERN.fullmatch(model) for model in models
        ):
            raise ValueError("contains an invalid model name")
        if len(models) != len(set(models)):
            raise ValueError("must not contain duplicate models")
        return ",".join(models)

    @field_validator("devin_default_model")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_default_model(self) -> BotSettings:
        if self.devin_default_model not in self.fallback_models:
            raise ValueError("DEVIN_DEFAULT_MODEL must be listed in DEVIN_MODELS")
        return self

    @property
    def fallback_models(self) -> tuple[str, ...]:
        return tuple(self.devin_models.split(","))


class ModelVariant(BaseModel):
    model_uid: str
    label: str
    cost_tier: str | None = None
    is_new: bool = False
    is_beta: bool = False


class ModelFamily(BaseModel):
    family_label: str
    family_uid: str
    slug: str
    aliases: list[str] = Field(default_factory=list)
    variants: list[ModelVariant]


class ModelCatalog(BaseModel):
    families: list[ModelFamily]

    @classmethod
    def fallback(cls, models: tuple[str, ...]) -> ModelCatalog:
        return cls(
            families=[
                ModelFamily(
                    family_label=model,
                    family_uid=model,
                    slug=model,
                    aliases=[],
                    variants=[ModelVariant(model_uid=model, label=model)],
                )
                for model in models
            ]
        )

    def family_contains(self, index: int, model: str) -> bool:
        family = self.families[index]
        return model in family.aliases or any(
            variant.model_uid == model for variant in family.variants
        )


class ModelCatalogError(RuntimeError):
    pass


class ModelCatalogLoader:
    def __init__(self, executable: str, project_dir: Path) -> None:
        self.executable = executable
        self.project_dir = project_dir

    async def load(self) -> ModelCatalog:
        logger.info("Loading Devin model catalog")
        process = await asyncio.create_subprocess_exec(
            self.executable,
            "models",
            "list",
            "--format",
            "json",
            cwd=self.project_dir,
            env=_devin_environment(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise ModelCatalogError("model discovery timed out") from exc
        if process.returncode != 0:
            raise ModelCatalogError("model discovery failed")
        try:
            catalog = ModelCatalog.model_validate(json.loads(stdout))
        except (ValueError, TypeError) as exc:
            raise ModelCatalogError("model discovery returned invalid JSON") from exc
        if not catalog.families:
            raise ModelCatalogError("model discovery returned no families")
        logger.info(
            "Loaded %d model families and %d variants",
            len(catalog.families),
            sum(len(family.variants) for family in catalog.families),
        )
        return catalog


@dataclass(frozen=True)
class DevinResult:
    returncode: int
    output: str
    cancelled: bool


class DevinRunner:
    def __init__(
        self,
        executable: str,
        project_dir: Path,
        sandbox: bool = True,
        permission_mode: str = "auto",
    ) -> None:
        self.executable = executable
        self.project_dir = project_dir
        self.sandbox = sandbox
        self.permission_mode = permission_mode
        self.process: asyncio.subprocess.Process | None = None
        self._cancelled = False

    def command(self, prompt: str, continue_session: bool, model: str) -> list[str]:
        command = [self.executable]
        if self.sandbox:
            command.append("--sandbox")
        command.extend(
            [
                "--permission-mode",
                self.permission_mode,
                "--respect-workspace-trust",
                "false",
                "--model",
                model,
            ]
        )
        if continue_session:
            command.append("--continue")
        return [*command, "--print", prompt]

    async def run(self, prompt: str, continue_session: bool, model: str) -> DevinResult:
        if self.process is not None:
            raise RuntimeError("Devin is already running")
        self._cancelled = False
        started_at = time.monotonic()
        logger.info(
            "Starting Devin turn model=%s continue=%s sandbox=%s permission_mode=%s cwd=%s",
            model,
            continue_session,
            self.sandbox,
            self.permission_mode,
            self.project_dir,
        )
        self.process = await asyncio.create_subprocess_exec(
            *self.command(prompt, continue_session, model),
            cwd=self.project_dir,
            env=_devin_environment(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        pid = self.process.pid
        logger.info("Devin process started pid=%d", pid)
        try:
            stdout, stderr = await self.process.communicate()
            returncode = self.process.returncode or 0
            logger.info(
                "Devin process finished pid=%d exit=%d duration=%.1fs stdout_bytes=%d stderr_bytes=%d cancelled=%s",
                pid,
                returncode,
                time.monotonic() - started_at,
                len(stdout),
                len(stderr),
                self._cancelled,
            )
            output = stdout.decode(errors="replace").strip()
            if not output:
                output = stderr.decode(errors="replace").strip()
            return DevinResult(returncode, output, self._cancelled)
        except asyncio.CancelledError:
            logger.info("Devin task cancelled pid=%d", pid)
            await self.cancel()
            raise
        finally:
            self.process = None

    async def cancel(self) -> bool:
        if self.process is None or self.process.returncode is not None:
            return False
        self._cancelled = True
        pid = self.process.pid
        logger.info("Terminating Devin process pid=%d", pid)
        self.process.terminate()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=5)
            logger.info("Devin process terminated pid=%d", pid)
        except TimeoutError:
            logger.warning("Killing unresponsive Devin process pid=%d", pid)
            self.process.kill()
            await self.process.wait()
        return True


class DevinTelegramBot:
    def __init__(
        self,
        settings: BotSettings,
        runner: DevinRunner,
        catalog_loader: ModelCatalogLoader,
    ) -> None:
        self.settings = settings
        self.runner = runner
        self.catalog_loader = catalog_loader
        self.catalog = ModelCatalog.fallback(settings.fallback_models)
        self.selected_model = settings.devin_default_model
        self.continue_session = False
        self._task: asyncio.Task[None] | None = None
        self._started_at: float | None = None

    @property
    def busy(self) -> bool:
        return self._task is not None and not self._task.done()

    def register(self, application: Application) -> None:
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
        application.add_handler(CommandHandler("model", self.model, filters=authorized))
        application.add_handler(
            CallbackQueryHandler(self.model_callback, pattern=r"^m[fpvabrx]:")
        )
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND & authorized, self.prompt)
        )

    async def setup(self, application: Application) -> None:
        await application.bot.set_my_commands(
            [
                BotCommand("new", "Start a new Devin session"),
                BotCommand("model", "Select the Devin model"),
                BotCommand("status", "Show the current state"),
                BotCommand("cancel", "Stop the active turn"),
            ]
        )
        await self.refresh_catalog()
        logger.info(
            "Telegram bot started for project %s with %d model families",
            self.settings.devin_project_dir,
            len(self.catalog.families),
        )

    async def refresh_catalog(self) -> bool:
        try:
            self.catalog = await self.catalog_loader.load()
            return True
        except ModelCatalogError as exc:
            logger.warning("%s; using configured model fallback", exc)
            return False

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(
            update,
            "/new — start a new session\n/model — select the model\n/status — show current state\n/cancel — stop the active turn",
        )

    async def new(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.busy:
            await self._reply(
                update, "Cancel the active turn before starting a new session."
            )
            return
        self.continue_session = False
        logger.info("Next prompt will start a new Devin session")
        await self._reply(update, "The next prompt will start a new Devin session.")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.busy or self._started_at is None:
            await self._reply(update, f"Devin is idle. Model: {self.selected_model}.")
            return
        elapsed = int(time.monotonic() - self._started_at)
        minutes, seconds = divmod(elapsed, 60)
        await self._reply(
            update,
            f"Devin is working. Model: {self.selected_model}. Elapsed: {minutes}m {seconds:02d}s.",
        )

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        cancelled = await self.runner.cancel()
        await self._reply(
            update,
            "Cancellation requested." if cancelled else "Devin is idle.",
        )

    async def model(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if context.args == ["refresh"]:
            refreshed = await self.refresh_catalog()
            await self._reply(
                update,
                "Model catalog refreshed."
                if refreshed
                else "Model refresh failed; using the previous catalog.",
            )
        await self._show_families(update, 0)

    async def model_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        if query is None:
            return
        if (
            query.from_user.id != self.settings.telegram_allowed_user_id
            or query.message is None
            or query.message.chat.type != "private"
        ):
            await query.answer("Not authorized", show_alert=True)
            return
        parts = (query.data or "").split(":")
        try:
            action = parts[0]
            if action == "mf":
                await query.answer()
                await self._show_families(update, int(parts[1]), edit=True)
            elif action == "mx":
                refreshed = await self.refresh_catalog()
                await query.answer(
                    "Model catalog refreshed" if refreshed else "Refresh failed"
                )
                await self._show_families(update, 0, edit=True)
            elif action == "mb":
                await query.answer()
                await self._show_families(update, 0, edit=True)
            elif action == "mv":
                await query.answer()
                await self._show_variants(
                    update, int(parts[1]), int(parts[2]), edit=True
                )
            elif action == "mp":
                await query.answer()
                await self._show_variants(update, int(parts[1]), 0, edit=True)
            elif action in {"ma", "mr"}:
                await self._select_catalog_model(query, parts)
        except IndexError:
            await query.answer(
                "The model catalog changed; reopen /model", show_alert=True
            )
        except ValueError:
            await query.answer(
                "The model catalog changed; reopen /model", show_alert=True
            )

    async def _show_families(
        self, update: Update, page: int, edit: bool = False
    ) -> None:
        total_pages = max(
            1,
            (len(self.catalog.families) + _FAMILIES_PER_PAGE - 1) // _FAMILIES_PER_PAGE,
        )
        page = max(0, min(page, total_pages - 1))
        start = page * _FAMILIES_PER_PAGE
        buttons = []
        for index in range(
            start, min(start + _FAMILIES_PER_PAGE, len(self.catalog.families))
        ):
            family = self.catalog.families[index]
            selected = (
                "✓ " if self.catalog.family_contains(index, self.selected_model) else ""
            )
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{selected}{family.family_label}", callback_data=f"mp:{index}"
                    )
                ]
            )
        navigation = []
        if page > 0:
            navigation.append(
                InlineKeyboardButton("‹ Previous", callback_data=f"mf:{page - 1}")
            )
        navigation.append(
            InlineKeyboardButton(
                f"{page + 1}/{total_pages}", callback_data=f"mf:{page}"
            )
        )
        if page + 1 < total_pages:
            navigation.append(
                InlineKeyboardButton("Next ›", callback_data=f"mf:{page + 1}")
            )
        buttons.append(navigation)
        buttons.append([InlineKeyboardButton("Refresh catalog", callback_data="mx:0")])
        await self._render_model_menu(
            update,
            f"Current model: {self.selected_model}\nChoose a model family:",
            InlineKeyboardMarkup(buttons),
            edit,
        )

    async def _show_variants(
        self, update: Update, family_index: int, page: int, edit: bool = False
    ) -> None:
        family = self.catalog.families[family_index]
        total_pages = max(
            1, (len(family.variants) + _VARIANTS_PER_PAGE - 1) // _VARIANTS_PER_PAGE
        )
        page = max(0, min(page, total_pages - 1))
        start = page * _VARIANTS_PER_PAGE
        buttons = []
        for alias_index, alias in enumerate(family.aliases):
            selected = "✓ " if alias == self.selected_model else ""
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{selected}Recommended ({alias})",
                        callback_data=f"ma:{family_index}:{alias_index}",
                    )
                ]
            )
        for variant_index in range(
            start, min(start + _VARIANTS_PER_PAGE, len(family.variants))
        ):
            variant = family.variants[variant_index]
            selected = "✓ " if variant.model_uid == self.selected_model else ""
            suffix = " · New" if variant.is_new else ""
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{selected}{variant.label}{suffix}",
                        callback_data=f"mr:{family_index}:{variant_index}",
                    )
                ]
            )
        navigation = []
        if page > 0:
            navigation.append(
                InlineKeyboardButton(
                    "‹ Previous", callback_data=f"mv:{family_index}:{page - 1}"
                )
            )
        if total_pages > 1:
            navigation.append(
                InlineKeyboardButton(
                    f"{page + 1}/{total_pages}",
                    callback_data=f"mv:{family_index}:{page}",
                )
            )
        if page + 1 < total_pages:
            navigation.append(
                InlineKeyboardButton(
                    "Next ›", callback_data=f"mv:{family_index}:{page + 1}"
                )
            )
        if navigation:
            buttons.append(navigation)
        buttons.append([InlineKeyboardButton("‹ Families", callback_data="mb:0")])
        await self._render_model_menu(
            update,
            f"{family.family_label}\nChoose a model variant:",
            InlineKeyboardMarkup(buttons),
            edit,
        )

    async def _select_catalog_model(self, query, parts: list[str]) -> None:
        if self.busy:
            await query.answer("Wait for the active turn to finish", show_alert=True)
            return
        family = self.catalog.families[int(parts[1])]
        if parts[0] == "ma":
            selected = family.aliases[int(parts[2])]
            label = f"{family.family_label} ({selected})"
        else:
            variant = family.variants[int(parts[2])]
            selected = variant.model_uid
            label = variant.label
        previous_model = self.selected_model
        self.selected_model = selected
        logger.info("Model changed from %s to %s", previous_model, selected)
        await query.answer(f"Selected {label}")
        await query.edit_message_text(f"Model selected: {label}\nID: {selected}")

    async def _render_model_menu(
        self,
        update: Update,
        text: str,
        markup: InlineKeyboardMarkup,
        edit: bool,
    ) -> None:
        if edit and update.callback_query is not None:
            await update.callback_query.edit_message_text(text, reply_markup=markup)
        else:
            await self._reply(update, text, reply_markup=markup)

    async def prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None or not message.text:
            return
        if self.busy:
            await self._reply(
                update, "Devin is already working. Try again after it finishes."
            )
            return
        logger.info(
            "Accepted Telegram prompt model=%s continue=%s prompt_chars=%d",
            self.selected_model,
            self.continue_session,
            len(message.text.strip()),
        )
        await self._reply(update, f"Devin started working with {self.selected_model}.")
        self._started_at = time.monotonic()
        self._task = asyncio.create_task(
            self._run_prompt(context.bot, message.chat_id, message.text.strip())
        )

    async def _run_prompt(self, bot: Bot, chat_id: int, prompt: str) -> None:
        try:
            result = await self.runner.run(
                prompt, self.continue_session, self.selected_model
            )
            if result.cancelled:
                response = (
                    "Devin was cancelled. The repository may contain partial changes."
                )
            elif result.returncode == 0:
                self.continue_session = True
                response = f"Devin finished this turn.\n\n{result.output}"
            else:
                response = f"Devin failed with exit code {result.returncode}.\n\n{result.output}"
            await self._send(bot, chat_id, response)
            logger.info(
                "Delivered Devin response exit=%d response_chars=%d",
                result.returncode,
                len(response),
            )
        except Exception as exc:
            logger.error("Devin turn failed: %s", type(exc).__name__)
            await self._send(
                bot, chat_id, "Devin failed unexpectedly. Check the service logs."
            )
        finally:
            self._started_at = None
            self._task = None

    async def _reply(
        self,
        update: Update,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        message = update.effective_message
        if message is not None:
            await message.reply_text(text, reply_markup=reply_markup)

    async def _send(self, bot: Bot, chat_id: int, text: str) -> None:
        text = text or "Devin finished without producing output."
        for start in range(0, len(text), 4000):
            await bot.send_message(chat_id, text[start : start + 4000])


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Telegram handler failed: %s", type(context.error).__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    settings = BotSettings()
    bot = DevinTelegramBot(
        settings,
        DevinRunner(
            settings.devin_executable,
            settings.devin_project_dir,
            settings.devin_sandbox,
            settings.devin_permission_mode,
        ),
        ModelCatalogLoader(settings.devin_executable, settings.devin_project_dir),
    )
    application = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token.get_secret_value())
        .post_init(bot.setup)
        .build()
    )
    bot.register(application)
    application.add_error_handler(handle_error)
    application.run_polling(
        allowed_updates=["message", "callback_query"], drop_pending_updates=True
    )
