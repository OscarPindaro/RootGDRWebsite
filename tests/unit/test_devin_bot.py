import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from devin_bot.bot import (
    BotSettings,
    DevinResult,
    DevinRunner,
    DevinTelegramBot,
    ModelCatalog,
    _devin_environment,
)

pytestmark = pytest.mark.unit


class MessageStub:
    def __init__(self, text: str = "", chat_id: int = 7) -> None:
        self.text = text
        self.chat_id = chat_id
        self.replies: list[tuple[str, Any]] = []

    async def reply_text(self, text: str, reply_markup: Any = None) -> None:
        self.replies.append((text, reply_markup))


class BotStub:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))


class ApplicationStub:
    def create_task(self, coroutine, update=None) -> asyncio.Task:
        return asyncio.create_task(coroutine)


class QueryStub:
    def __init__(self, data: str) -> None:
        self.from_user = SimpleNamespace(id=7)
        self.message = SimpleNamespace(chat=SimpleNamespace(type="private"))
        self.data = data
        self.answers: list[str] = []
        self.edited: tuple[str, Any] | None = None

    async def answer(self, text: str = "", show_alert: bool = False) -> None:
        self.answers.append(text)

    async def edit_message_text(self, text: str, reply_markup: Any = None) -> None:
        self.edited = (text, reply_markup)


class ContextStub:
    def __init__(self) -> None:
        self.bot = BotStub()
        self.application = ApplicationStub()
        self.args: list[str] = []


class RunnerStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool, str]] = []
        self.cancelled = False

    async def run(self, prompt: str, continue_session: bool, model: str) -> DevinResult:
        self.calls.append((prompt, continue_session, model))
        return DevinResult(0, f"reply: {prompt}", False)

    async def cancel(self) -> bool:
        self.cancelled = True
        return True


class BlockingRunner(RunnerStub):
    def __init__(self) -> None:
        super().__init__()
        self.release = asyncio.Event()

    async def run(self, prompt: str, continue_session: bool, model: str) -> DevinResult:
        self.calls.append((prompt, continue_session, model))
        await self.release.wait()
        return DevinResult(0, "done", False)


class SleepingRunner(DevinRunner):
    def command(self, prompt: str, continue_session: bool, model: str) -> list[str]:
        return [self.executable, "-c", "import time; time.sleep(60)"]


def settings(tmp_path: Path, **values: Any) -> BotSettings:
    return BotSettings(
        telegram_bot_token="token",
        telegram_allowed_user_id=7,
        devin_project_dir=tmp_path,
        devin_executable=sys.executable,
        **values,
    )


class CatalogLoaderStub:
    async def load(self) -> ModelCatalog:
        return ModelCatalog.fallback(("adaptive", "gpt", "opus", "swe"))


def make_bot(tmp_path: Path, runner: RunnerStub) -> DevinTelegramBot:
    return DevinTelegramBot(settings(tmp_path), runner, CatalogLoaderStub())


def update(text: str = "") -> SimpleNamespace:
    return SimpleNamespace(effective_message=MessageStub(text))


async def wait_until_idle(bot: DevinTelegramBot) -> None:
    while bot.busy:
        await asyncio.sleep(0)


def test_devin_environment_excludes_telegram_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "7")
    monkeypatch.setenv("PATH", "/usr/bin")

    environment = _devin_environment()

    assert "TELEGRAM_BOT_TOKEN" not in environment
    assert "TELEGRAM_ALLOWED_USER_ID" not in environment
    assert environment["PATH"] == "/usr/bin"


def test_settings_normalize_model_choices(tmp_path: Path) -> None:
    configured = settings(
        tmp_path,
        devin_models=" adaptive, gpt,opus ",
        devin_default_model="gpt",
    )

    assert configured.fallback_models == ("adaptive", "gpt", "opus")


def test_settings_reject_default_outside_choices(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="DEVIN_DEFAULT_MODEL"):
        settings(tmp_path, devin_models="gpt,opus", devin_default_model="adaptive")


def test_catalog_accepts_devin_model_schema() -> None:
    catalog = ModelCatalog.model_validate(
        {
            "families": [
                {
                    "family_label": "Claude Opus 5",
                    "family_uid": "claude-opus-5",
                    "slug": "claude-opus-5",
                    "aliases": ["opus"],
                    "variants": [
                        {
                            "model_uid": "claude-opus-5-high",
                            "label": "Claude Opus 5 High",
                            "cost_tier": "High cost",
                            "is_new": True,
                            "is_beta": False,
                        }
                    ],
                }
            ]
        }
    )

    assert catalog.families[0].aliases == ["opus"]
    assert catalog.families[0].variants[0].model_uid == "claude-opus-5-high"


async def test_model_family_menu_is_paginated(tmp_path: Path) -> None:
    bot = make_bot(tmp_path, RunnerStub())
    bot.catalog = ModelCatalog.fallback(tuple(f"model-{index}" for index in range(9)))
    request = update()

    await bot.model(request, ContextStub())

    markup = request.effective_message.replies[0][1]
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert "Next ›" in labels
    assert "model-8" not in labels


def test_runner_builds_sandboxed_model_command(tmp_path: Path) -> None:
    runner = DevinRunner("devin", tmp_path)

    assert runner.command("continue", True, "opus") == [
        "devin",
        "--sandbox",
        "--permission-mode",
        "auto",
        "--respect-workspace-trust",
        "false",
        "--model",
        "opus",
        "--continue",
        "--print",
        "continue",
    ]


def test_runner_builds_unsandboxed_dangerous_command(tmp_path: Path) -> None:
    runner = DevinRunner("devin", tmp_path, sandbox=False, permission_mode="dangerous")

    command = runner.command("edit", False, "adaptive")

    assert "--sandbox" not in command
    assert command[:3] == ["devin", "--permission-mode", "dangerous"]


async def test_cancelling_run_terminates_child_process(tmp_path: Path) -> None:
    runner = SleepingRunner(sys.executable, tmp_path)
    task = asyncio.create_task(runner.run("ignored", False, "adaptive"))
    while runner.process is None:
        await asyncio.sleep(0)
    process = runner.process

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert process.returncode is not None
    assert runner.process is None


async def test_bot_continues_after_first_successful_turn(tmp_path: Path) -> None:
    runner = RunnerStub()
    bot = make_bot(tmp_path, runner)
    context = ContextStub()

    await bot.prompt(update("first"), context)
    await wait_until_idle(bot)
    await bot.prompt(update("answer to clarification"), context)
    await wait_until_idle(bot)

    assert runner.calls == [
        ("first", False, "adaptive"),
        ("answer to clarification", True, "adaptive"),
    ]
    assert context.bot.messages[-1] == (
        7,
        "Devin finished this turn.\n\nreply: answer to clarification",
    )


async def test_new_resets_continuation(tmp_path: Path) -> None:
    runner = RunnerStub()
    bot = make_bot(tmp_path, runner)
    context = ContextStub()

    await bot.prompt(update("first"), context)
    await wait_until_idle(bot)
    await bot.new(update(), context)
    await bot.prompt(update("second"), context)
    await wait_until_idle(bot)

    assert runner.calls == [
        ("first", False, "adaptive"),
        ("second", False, "adaptive"),
    ]


async def test_busy_bot_rejects_another_prompt(tmp_path: Path) -> None:
    runner = BlockingRunner()
    bot = make_bot(tmp_path, runner)
    context = ContextStub()
    second = update("second")

    await bot.prompt(update("first"), context)
    await asyncio.sleep(0)
    await bot.prompt(second, context)
    runner.release.set()
    await wait_until_idle(bot)

    assert runner.calls == [("first", False, "adaptive")]
    assert second.effective_message.replies[0][0] == (
        "Devin is already working. Try again after it finishes."
    )


async def test_model_selection_is_used_by_next_turn(tmp_path: Path) -> None:
    runner = RunnerStub()
    bot = make_bot(tmp_path, runner)
    context = ContextStub()
    query = QueryStub("mr:2:0")

    await bot.model_callback(SimpleNamespace(callback_query=query), context)
    await bot.prompt(update("use selected model"), context)
    await wait_until_idle(bot)

    assert bot.selected_model == "opus"
    assert runner.calls == [("use selected model", False, "opus")]


async def test_prompt_logs_metadata_without_content(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    bot = make_bot(tmp_path, RunnerStub())

    with caplog.at_level(logging.INFO, logger="devin_bot.bot"):
        await bot.prompt(update("private prompt"), ContextStub())
        await wait_until_idle(bot)

    assert "prompt_chars=14" in caplog.text
    assert "private prompt" not in caplog.text


async def test_cancel_is_forwarded_to_runner(tmp_path: Path) -> None:
    runner = RunnerStub()
    bot = make_bot(tmp_path, runner)
    request = update()

    await bot.cancel(request, ContextStub())

    assert runner.cancelled
    assert request.effective_message.replies[0][0] == "Cancellation requested."
