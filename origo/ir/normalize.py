from __future__ import annotations

from typing import Any

from origo.ir.models import TrajectoryIR, TrajectoryRole, TrajectoryStep, TrajectorySubstep
from origo.schema.trace import TraceRun, TraceSpan


def trace_to_trajectory_ir(trace: TraceRun) -> TrajectoryIR:
    """Normalize Origo's v0 trace schema into the trajectory IR.

    This keeps the legacy local JSON fixture format usable while giving later
    analysis stages a step/substep structure closer to AgentRx-style trajectory
    processing.
    """

    return TrajectoryIR(
        trajectory_id=trace.run_id,
        instruction=trace.task,
        steps=[_span_to_step(index, span) for index, span in enumerate(trace.spans)],
        metadata={
            **trace.metadata,
            "source_schema": "origo.trace.v0",
            "final_output_span_id": trace.final_output_span_id,
        },
    )


def _span_to_step(index: int, span: TraceSpan) -> TrajectoryStep:
    substeps: list[TrajectorySubstep] = []
    if span.input is not None:
        substeps.append(_substep(span, "input", span.input, len(substeps)))
    if span.output is not None:
        substeps.append(_substep(span, "output", span.output, len(substeps)))

    return TrajectoryStep(
        index=index,
        span_id=span.id,
        name=span.name,
        kind=span.kind,
        substeps=substeps,
        parent_span_id=span.parent_id,
        start_time=span.started_at,
        end_time=span.ended_at,
        attributes=span.metadata,
    )


def _substep(span: TraceSpan, field_name: str, content: Any, sub_index: int) -> TrajectorySubstep:
    return TrajectorySubstep(
        sub_index=sub_index,
        role=_role_for(span, field_name),
        content=content,
        artifact_ids=[f"{span.id}.{field_name}"],
        source_span_id=span.id,
        metadata={"field": field_name},
    )


def _role_for(span: TraceSpan, field_name: str) -> TrajectoryRole:
    if span.kind == "user_input":
        return "user"
    if span.kind in {"system_prompt", "prompt_assembly"}:
        return "system"
    if span.kind in {"retrieval", "retrieved_chunk", "rerank"}:
        return "retriever"
    if span.kind in {"tool_call", "tool_result"}:
        return "tool"
    if span.kind in {"memory_read", "memory_write"}:
        return "memory"
    if span.kind == "validator":
        return "validator"
    if span.kind in {"llm_call", "context_summary", "final_output"}:
        return "assistant"
    return "agent"
