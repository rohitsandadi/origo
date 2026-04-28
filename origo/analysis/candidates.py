from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CulpritCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    span_id: str
    score: float
    reasons: list[str] = Field(default_factory=list)
    ignored_evidence_span_ids: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    path: list[str] = Field(default_factory=list)
