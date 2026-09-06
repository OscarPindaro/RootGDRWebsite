from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from .application import AcpTelegramApplication
from .config import AcpBotSettings
from .probe import AcpProbe
from .storage import StateDatabase
from .storage.migrations import upgrade


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="devin-telegram-acp")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run")
    subparsers.add_parser("db-upgrade")
    probe = subparsers.add_parser("acp-probe")
    probe.add_argument("--cwd", type=Path, default=Path.cwd())
    probe.add_argument("--executable", default="devin")
    probe.add_argument("--timeout", type=float, default=30)
    probe.add_argument("--exercise", action="store_true")
    probe.add_argument(
        "--prompt", default="Reply with ACP_PROBE_OK without using tools."
    )
    return parser


async def run_probe(args: argparse.Namespace) -> int:
    result = await AcpProbe(args.executable, args.cwd, args.timeout).run(
        exercise=args.exercise,
        prompt=args.prompt,
    )
    print(result.model_dump_json(indent=2, by_alias=True))
    return 1 if result.error else 0


def run_bot(settings: AcpBotSettings) -> None:
    upgrade(settings.devin_state_path)
    database = StateDatabase(settings.devin_state_path)
    runtime = AcpTelegramApplication(settings, database)
    runtime.build().run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main() -> None:
    configure_logging()
    args = build_parser().parse_args()
    if args.command == "acp-probe":
        raise SystemExit(asyncio.run(run_probe(args)))
    settings = AcpBotSettings()
    if args.command == "db-upgrade":
        upgrade(settings.devin_state_path)
        return
    run_bot(settings)
