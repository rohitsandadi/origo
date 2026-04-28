from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from origo.schema.trace import TraceRun, TraceSpan


def load_traceroot_json(path: str | Path) -> TraceRun:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return traceroot_json_to_trace(data)


def traceroot_json_to_trace(data: dict[str, Any]) -> TraceRun:
    traces = data.get("traces") or []
    spans_data = data.get("spans") or []
    if not spans_data:
        raise ValueError("No TraceRoot spans found")

    trace_record = traces[0] if traces else {"trace_id": spans_data[0].get("trace_id")}
    trace_id = str(trace_record.get("trace_id") or trace_record.get("id"))
    trace_output = trace_record.get("output")
    spans: list[TraceSpan] = []
    final_output_span_id: str | None = None

    for span_data in spans_data:
        if str(span_data.get("trace_id")) != trace_id:
            continue
        span = _span_record_to_trace_span(span_data)
        if span.output == trace_output and span.kind in {"llm_call", "planner_step"}:
            span.kind = "final_output"
            final_output_span_id = span.id
        spans.append(span)

    if not spans:
        raise ValueError(f"No TraceRoot spans found for trace {trace_id}")

    if final_output_span_id is None:
        for span in reversed(spans):
            if span.kind == "llm_call" and span.output is not None:
                span.kind = "final_output"
                final_output_span_id = span.id
                break

    return TraceRun(
        run_id=trace_id,
        task=_string_or_none(trace_record.get("input")),
        spans=spans,
        final_output_span_id=final_output_span_id,
        metadata={
            "source_schema": "traceroot.clickhouse_json",
            **_optional_trace_metadata(trace_record),
        },
    )


def _span_record_to_trace_span(span_data: dict[str, Any]) -> TraceSpan:
    return TraceSpan(
        id=str(span_data.get("span_id")),
        parent_id=span_data.get("parent_span_id"),
        kind=_span_kind(str(span_data.get("span_kind") or "")),
        name=span_data.get("name"),
        input=_maybe_json(span_data.get("input")),
        output=_maybe_json(span_data.get("output")),
        metadata=_span_metadata(span_data),
        started_at=_time_to_float(span_data.get("span_start_time")),
        ended_at=_time_to_float(span_data.get("span_end_time")),
    )


def _span_kind(kind: str) -> str:
    normalized = kind.upper()
    if normalized == "TOOL":
        return "tool_result"
    if normalized == "LLM":
        return "llm_call"
    if normalized == "AGENT":
        return "planner_step"
    return "planner_step"


def _span_metadata(span_data: dict[str, Any]) -> dict[str, Any]:
    metadata = _maybe_json(span_data.get("metadata"))
    if not isinstance(metadata, dict):
        metadata = {}
    for key in ("git_source_file", "git_source_line", "git_source_function", "model_name", "status"):
        if key in span_data and span_data[key] is not None:
            metadata[key] = span_data[key]
    return metadata


def _optional_trace_metadata(trace_record: dict[str, Any]) -> dict[str, Any]:
    metadata = {}
    for key in ("git_repo", "git_ref", "name", "user_id", "session_id"):
        if key in trace_record and trace_record[key] is not None:
            metadata[key] = trace_record[key]
    return metadata


def _maybe_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or stripped[0] not in "{[":
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _time_to_float(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None
