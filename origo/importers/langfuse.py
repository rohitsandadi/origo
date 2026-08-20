from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from origo.importers.common import optional_identifier, parse_timestamp, require_identifier
from origo.schema.trace import TraceRun, TraceSpan


def load_langfuse_json(path: str | Path) -> TraceRun:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return langfuse_json_to_trace(data)


def langfuse_json_to_trace(data: dict[str, Any]) -> TraceRun:
    trace_data = data.get("trace") or data
    trace_id = str(trace_data.get("id") or trace_data.get("traceId") or "langfuse-trace")
    observations = list(data.get("observations") or trace_data.get("observations") or [])
    scores = list(data.get("scores") or trace_data.get("scores") or [])
    scores_by_observation = _scores_by_observation(scores)

    spans: list[TraceSpan] = []
    trace_input = trace_data.get("input")
    trace_output = trace_data.get("output")
    if trace_input is not None:
        spans.append(
            TraceSpan(
                id="trace.input",
                kind="user_input",
                name="trace input",
                output=trace_input,
            )
        )

    final_output_span_id: str | None = None
    for observation in observations:
        span = _observation_to_span(observation, scores_by_observation.get(str(observation.get("id")), []))
        if span.kind == "final_output":
            final_output_span_id = span.id
        spans.append(span)

    if final_output_span_id is None:
        for span in reversed(spans):
            if span.output == trace_output:
                final_output_span_id = span.id
                span.kind = "final_output"
                break

    if final_output_span_id is None and trace_output is not None:
        parent_id = spans[-1].id if spans else None
        final_output_span_id = "trace.output"
        spans.append(
            TraceSpan(
                id=final_output_span_id,
                parent_id=parent_id,
                kind="final_output",
                name="trace output",
                output=trace_output,
            )
        )

    return TraceRun(
        run_id=trace_id,
        task=_string_or_none(trace_input),
        spans=spans,
        final_output_span_id=final_output_span_id,
        metadata={
            **_dict_or_empty(trace_data.get("metadata")),
            "source_schema": "langfuse.json_export",
            "langfuse_trace_name": trace_data.get("name"),
        },
    )


def _observation_to_span(observation: dict[str, Any], scores: list[dict[str, Any]]) -> TraceSpan:
    observation_id = require_identifier(observation.get("id"), field="Langfuse observation id")
    output = observation.get("output")
    kind = _observation_kind(str(observation.get("type") or ""), output)
    metadata = {
        **_dict_or_empty(observation.get("metadata")),
        "langfuse_type": observation.get("type"),
    }
    if scores:
        metadata["langfuse_scores"] = scores
    return TraceSpan(
        id=observation_id,
        parent_id=optional_identifier(
            observation.get("parentObservationId") or observation.get("parent_observation_id")
        ),
        kind=kind,
        name=observation.get("name"),
        input=observation.get("input"),
        output=output,
        metadata=metadata,
        started_at=parse_timestamp(observation.get("startTime") or observation.get("start_time")),
        ended_at=parse_timestamp(observation.get("endTime") or observation.get("end_time")),
    )


def _observation_kind(kind: str, output: Any) -> str:
    normalized = kind.upper()
    if normalized in {"TOOL", "TOOL_RESULT"}:
        return "tool_result" if output is not None else "tool_call"
    if normalized in {"RETRIEVER", "RETRIEVAL"}:
        return "retrieval"
    if normalized in {"GENERATION", "LLM"}:
        return "llm_call"
    if normalized in {"EVENT"}:
        return "state_update"
    return "planner_step"


def _scores_by_observation(scores: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for score in scores:
        observation_id = score.get("observationId") or score.get("observation_id")
        if observation_id is None:
            continue
        result.setdefault(str(observation_id), []).append(score)
    return result


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None
