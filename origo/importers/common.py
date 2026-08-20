from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def require_identifier(value: Any, *, field: str) -> str:
    """Return a normalized identifier or fail with an importer-level error."""

    identifier = optional_identifier(value)
    if identifier is None:
        raise ValueError(f"{field} is missing")
    return identifier


def optional_identifier(value: Any) -> str | None:
    if value is None:
        return None
    identifier = str(value).strip()
    return identifier or None


def parse_timestamp(value: Any) -> float | None:
    """Convert numeric or ISO-8601 timestamps to Unix seconds when possible."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None

    candidate = value.strip()
    if not candidate:
        return None
    try:
        return float(candidate)
    except ValueError:
        pass

    if candidate.endswith(("Z", "z")):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()
