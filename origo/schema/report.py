from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from origo.schema.graph import TraceGraph


class OutputClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    source_span_id: str
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    time_scope: str | None = None
    confidence: float | None = None


class OutputAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    action_type: str
    arguments: dict[str, object]
    source_span_id: str
    target: str | None = None
    risk_level: str | None = None


class IgnoredEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    span_id: str
    snippet: str
    issue: str
    edge_kind: str


class CulpritCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    confidence: float
    culprit_span_id: str
    culprit_snippet: str
    path: list[str] = Field(default_factory=list)
    ignored_evidence_span_ids: list[str] = Field(default_factory=list)
    ignored_evidence: list[IgnoredEvidence] = Field(default_factory=list)
    failed_check_ids: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    suggested_fixes: list[str] = Field(default_factory=list)
    why_suspicious: list[str] = Field(default_factory=list)


class TracebackReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    failure_id: str
    bad_output: str
    expected: str | None = None
    cards: list[CulpritCard] = Field(default_factory=list)
    graph: TraceGraph | None = None
    missing_evidence: list[str] = Field(default_factory=list)
