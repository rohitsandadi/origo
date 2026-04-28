from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    invariant_id: str | None = None
    check_name: str
    target_step_id: str | None = None
    target_artifact_id: str | None = None
    status: Literal["pass", "fail", "skip", "error", "unknown"]
    failure_mode: str | None = None
    explanation: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float
    checker_kind: Literal["deterministic", "python", "llm_judge", "replay"] = "deterministic"
