from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SpanKind = Literal[
    "user_input",
    "system_prompt",
    "prompt_assembly",
    "llm_call",
    "retrieval",
    "retrieved_chunk",
    "rerank",
    "context_summary",
    "tool_call",
    "tool_result",
    "memory_read",
    "memory_write",
    "planner_step",
    "router_decision",
    "validator",
    "parser",
    "state_update",
    "final_output",
    "error",
]


class TraceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    parent_id: str | None = None
    kind: SpanKind
    name: str | None = None
    input: Any | None = None
    output: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: float | None = None
    ended_at: float | None = None


class TraceRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    task: str | None = None
    spans: list[TraceSpan]
    final_output_span_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_span_references(self) -> "TraceRun":
        seen: set[str] = set()
        duplicates: set[str] = set()
        for span in self.spans:
            if span.id in seen:
                duplicates.add(span.id)
            seen.add(span.id)
        if duplicates:
            duplicate_list = ", ".join(sorted(duplicates))
            raise ValueError(f"Duplicate span id: {duplicate_list}")

        for span in self.spans:
            if span.parent_id is not None and span.parent_id not in seen:
                raise ValueError(f"Unknown parent_id '{span.parent_id}' for span '{span.id}'")

        if self.final_output_span_id is not None and self.final_output_span_id not in seen:
            raise ValueError(f"Unknown final_output_span_id '{self.final_output_span_id}'")

        return self

    @property
    def span_ids(self) -> set[str]:
        return {span.id for span in self.spans}

    def get_span(self, span_id: str) -> TraceSpan:
        for span in self.spans:
            if span.id == span_id:
                return span
        raise KeyError(span_id)

    def final_output_span(self) -> TraceSpan | None:
        if self.final_output_span_id:
            return self.get_span(self.final_output_span_id)
        for span in reversed(self.spans):
            if span.kind == "final_output":
                return span
        return None
