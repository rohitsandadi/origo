from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


TrajectoryRole = Literal[
    "user",
    "system",
    "assistant",
    "tool",
    "retriever",
    "memory",
    "validator",
    "agent",
]

ArtifactKind = Literal[
    "message",
    "prompt",
    "retrieved_document",
    "retrieved_chunk",
    "tool_call",
    "tool_result",
    "memory_item",
    "summary",
    "state",
    "validator_result",
    "final_output",
    "source_code_ref",
]


class TrajectorySubstep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sub_index: int
    role: TrajectoryRole
    content: Any
    artifact_ids: list[str] = Field(default_factory=list)
    source_span_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrajectoryStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    span_id: str | None = None
    name: str | None = None
    kind: str
    substeps: list[TrajectorySubstep] = Field(default_factory=list)
    parent_span_id: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class TrajectoryIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trajectory_id: str
    instruction: str | None = None
    steps: list[TrajectoryStep]
    metadata: dict[str, Any] = Field(default_factory=dict)


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: ArtifactKind
    span_id: str | None = None
    content: Any | None = None
    text: str | None = None
    created_at_step: int | None = None
    included_in_artifact_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
