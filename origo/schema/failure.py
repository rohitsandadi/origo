from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FailureType = Literal[
    "stale_retrieval",
    "ignored_tool_output",
    "unsupported_claim",
    "summary_corruption",
    "memory_conflict",
    "validator_gap",
    "wrong_tool_argument",
    "other",
]


class FailureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    failure_id: str
    final_output_span_id: str | None = None
    bad_output: str
    expected: str | None = None
    failure_type: FailureType | None = None
    notes: str | None = None
    expected_evidence_span_ids: list[str] = Field(default_factory=list)
