from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Invariant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    scope: Literal["static", "dynamic"]
    target_kinds: list[str] = Field(default_factory=list)
    trigger: str
    check_type: Literal["python", "structured", "llm_judge"]
    assertion: str
    code: str | None = None
    prompt: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


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
