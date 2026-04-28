from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class RunArtifactWriter:
    """Write auditable stage artifacts for one Origo analysis run."""

    def __init__(self, root: str | Path, run_id: str):
        self.root = Path(root)
        self.run_id = _safe_run_id(run_id)
        self.run_dir = self.root / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def write_json(self, name: str, value: Any) -> Path:
        path = self.run_dir / f"{name}.json"
        path.write_text(json.dumps(_jsonable(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def write_text(self, name: str, value: str) -> Path:
        path = self.run_dir / name
        path.write_text(value, encoding="utf-8")
        return path


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(child) for key, child in value.items()}
    return value


def _safe_run_id(run_id: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in run_id).strip("-") or "run"
