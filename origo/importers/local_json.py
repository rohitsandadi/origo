from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from origo.schema.failure import FailureSpec
from origo.schema.trace import TraceRun


def _read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def load_trace_json(path: str | Path) -> TraceRun:
    """Load a local JSON trace into Origo's canonical trace schema."""

    data = json.loads(_read_text(path))
    return TraceRun.model_validate(data)


def load_failure_yaml(path: str | Path) -> FailureSpec:
    """Load a local YAML failure spec into Origo's canonical failure schema."""

    data: Any = yaml.safe_load(_read_text(path))
    return FailureSpec.model_validate(data)
