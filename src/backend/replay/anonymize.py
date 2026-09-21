"""Anonymization of recorded data.

Recordings may be taken in production and replayed elsewhere, so
user-identifying values never reach the recording files. Emails and user
names are replaced with deterministic per-session pseudonyms: the same input
always maps to the same replacement within a session, so a replay stays
coherent while carrying no real identities. The mapping lives only in the
worker-shared recording config, which never leaves the machine.

Content that is not an identity (world names, page titles, …) is kept: the
replay needs it to reproduce the journey.
"""

from __future__ import annotations

import re

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@]+$")

# Keys whose string values are identities wherever they appear.
IDENTITY_KEYS = frozenset({"email"})
# Path prefixes where a "name" value identifies a person, not a piece of content.
IDENTITY_PATHS = ("/auth", "/api/users", "/api/admin")

_MAX_VALUE = 200


class Anonymizer:
    """Deterministic pseudonyms for the identities of one session."""

    def __init__(self, aliases: dict[str, str] | None = None) -> None:
        self._aliases: dict[str, str] = dict(aliases or {})

    @property
    def aliases(self) -> dict[str, str]:
        return dict(self._aliases)

    def scrub(self, payload: object, *, identity_path: bool = False) -> object:
        """Return a copy of the payload with identities replaced."""
        if isinstance(payload, dict):
            return {
                key: self._scrub(key, value, identity_path)
                for key, value in payload.items()
            }
        if isinstance(payload, list):
            return [self._scrub(None, item, identity_path) for item in payload]
        return payload

    def _scrub(self, key: str | None, value: object, identity_path: bool) -> object:
        if isinstance(value, dict):
            return self.scrub(value, identity_path=identity_path)
        if isinstance(value, list):
            return [self._scrub(key, item, identity_path) for item in value]
        if isinstance(value, str) and len(value) <= _MAX_VALUE:
            if key in IDENTITY_KEYS or (identity_path and key == "name"):
                return self._alias(value)
            if EMAIL.fullmatch(value):
                return self._alias(value)
        return value

    def _alias(self, original: str) -> str:
        if original not in self._aliases:
            if EMAIL.fullmatch(original):
                count = sum(1 for alias in self._aliases.values() if "@" in alias)
                self._aliases[original] = f"user-{count + 1}@example.test"
            else:
                count = sum(1 for value in self._aliases.values() if "@" not in value)
                self._aliases[original] = f"Utente {count + 1}"
        return self._aliases[original]
