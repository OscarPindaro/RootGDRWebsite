"""Collect a small, redacted diagnostic bundle from failed harness runs.

CI uploads diagnostics only when a job fails. This collector walks the harness
artifact runs, keeps an allowlist of file types from runs that failed, redacts
anything that looks like a credential and stops at a byte budget, so a run
never publishes the whole artifacts directory, an HTML report, a database dump,
an image archive or an environment file.

Usage:

    uv run python tools/ci/collect_artifacts.py \
        --root harness-artifacts --destination ci-artifacts
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

ALLOWED_SUFFIXES = frozenset({".xml", ".log", ".txt", ".png"})
FORBIDDEN_NAMES = frozenset({".env", "manifest.json"})
TOTAL_LIMIT = 10 * 1024 * 1024
PER_FILE_LIMIT = 2 * 1024 * 1024
REDACTION = "[redacted]"

# Anything shaped like a credential: a named secret, an authorization header or
# a bare bearer token. Deliberately conservative: a diagnostic bundle may lose
# a line, never a secret.
SECRET_PATTERNS = (
    # A named secret, with any prefix (`AUTH__JWT_SECRET=…`), never the name.
    re.compile(
        r"(?i)[\w.-]*(jwt[_ -]?secret|password|passwd|token|secret|api[_ -]?key|"
        r"authorization)[\w.-]*\s*[:=]\s*\S+"
    ),
    re.compile(r"(?i)\bbearer\s+\S+"),
    re.compile(r"(?i)\b(vk_|ghp_|github_pat_)[A-Za-z0-9_]{8,}"),
)


class CollectedFile(BaseModel):
    source: str
    destination: str
    bytes: int
    redacted: bool


class Collection(BaseModel):
    runs: list[str] = Field(default_factory=list)
    files: list[CollectedFile] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    total_bytes: int = 0


def redact(text: str) -> tuple[str, bool]:
    """Replace credential-shaped content; report whether anything changed."""
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(REDACTION, redacted)
    return redacted, redacted != text


def _failed_runs(root: Path) -> list[Path]:
    runs = []
    for manifest_file in sorted(root.glob("*/manifest.json")):
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue
        if manifest.get("status") in {"failed", "interrupted"}:
            runs.append(manifest_file.parent)
    return runs


def _wanted(path: Path) -> bool:
    if path.name in FORBIDDEN_NAMES:
        return False
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        return False
    return path.is_file()


def collect(root: Path, destination: Path) -> Collection:
    """Copy the allowlisted files of failed runs, redacted and size-capped."""
    collection = Collection()
    if not root.is_dir():
        return collection
    destination.mkdir(parents=True, exist_ok=True)
    for run in _failed_runs(root):
        collection.runs.append(run.name)
        for source in sorted(run.rglob("*")):
            if not _wanted(source):
                continue
            relative = source.relative_to(root)
            size = source.stat().st_size
            if size > PER_FILE_LIMIT or collection.total_bytes + size > TOTAL_LIMIT:
                collection.skipped.append(str(relative))
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix.lower() == ".png":
                shutil.copyfile(source, target)
                copied = size
                redacted = False
            else:
                text = source.read_text(encoding="utf-8", errors="replace")
                cleaned, redacted = redact(text)
                target.write_text(cleaned, encoding="utf-8")
                copied = len(cleaned.encode("utf-8"))
            collection.files.append(
                CollectedFile(
                    source=str(relative),
                    destination=str(target.relative_to(destination)),
                    bytes=copied,
                    redacted=redacted,
                )
            )
            collection.total_bytes += copied
    (destination / "collection.json").write_text(
        collection.model_dump_json(indent=2), encoding="utf-8"
    )
    return collection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("harness-artifacts"))
    parser.add_argument("--destination", type=Path, default=Path("ci-artifacts"))
    arguments = parser.parse_args()
    collection = collect(arguments.root, arguments.destination)
    print(
        f"collected {len(collection.files)} file(s) from "
        f"{len(collection.runs)} failed run(s), {collection.total_bytes} bytes, "
        f"{len(collection.skipped)} skipped"
    )


if __name__ == "__main__":
    main()
