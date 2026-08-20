from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from origo.importers.common import optional_identifier, parse_timestamp, require_identifier
from origo.schema.trace import TraceRun, TraceSpan


def load_phoenix_json(path: str | Path) -> TraceRun:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return phoenix_json_to_trace(data)


def phoenix_json_to_trace(data: dict[str, Any] | list[dict[str, Any]]) -> TraceRun:
    spans_data = data if isinstance(data, list) else data.get("spans", [])
    spans: list[TraceSpan] = []
    trace_ids: set[str] = set()
    final_output_span_id: str | None = None

    for span_data in spans_data:
        context = span_data.get("context", {})
        trace_id = require_identifier(
            context.get("trace_id") or context.get("traceId") or span_data.get("trace_id"),
            field="Phoenix trace id",
        )
        span_id = require_identifier(
            context.get("span_id") or context.get("spanId") or span_data.get("span_id"),
            field="Phoenix span id",
        )
        trace_ids.add(trace_id)

        attrs = span_data.get("attributes") or {}
        documents = _phoenix_documents(attrs)
        is_final = bool(_nested_get(attrs, ["origo", "final_output"]) or attrs.get("origo.final_output"))
        kind = _span_kind(str(span_data.get("span_kind") or attrs.get("openinference.span.kind") or ""), documents, is_final)
        if is_final:
            final_output_span_id = span_id

        spans.append(
            TraceSpan(
                id=span_id,
                parent_id=optional_identifier(span_data.get("parent_id") or span_data.get("parentId")),
                kind=kind,
                name=span_data.get("name"),
                input=_nested_get(attrs, ["input", "value"]) or attrs.get("input.value"),
                output=[f"{span_id}.document.{index}" for index, _ in enumerate(documents)] if documents else _nested_get(attrs, ["output", "value"]) or attrs.get("output.value"),
                metadata=_metadata(attrs),
                started_at=parse_timestamp(span_data.get("start_time") or span_data.get("startTime")),
                ended_at=parse_timestamp(span_data.get("end_time") or span_data.get("endTime")),
            )
        )
        for index, document in enumerate(documents):
            flat = _flatten_document(document)
            spans.append(
                TraceSpan(
                    id=f"{span_id}.document.{index}",
                    parent_id=span_id,
                    kind="retrieved_chunk",
                    name=str(flat.get("document.id") or f"retrieved document {index}"),
                    output=flat.get("document.content") or flat.get("content") or flat,
                    metadata={key: value for key, value in flat.items() if key != "document.content"},
                )
            )

    if not spans:
        raise ValueError("No Phoenix spans found")
    if len(trace_ids) != 1:
        raise ValueError("Phoenix importer currently expects exactly one trace")

    if final_output_span_id is None:
        for span in reversed(spans):
            if span.kind == "llm_call" and span.output is not None:
                span.kind = "final_output"
                final_output_span_id = span.id
                break

    return TraceRun(
        run_id=next(iter(trace_ids)),
        spans=spans,
        final_output_span_id=final_output_span_id,
        metadata={"source_schema": "phoenix.span_json"},
    )


def _span_kind(span_kind: str, documents: list[dict[str, Any]], is_final: bool) -> str:
    if is_final:
        return "final_output"
    normalized = span_kind.upper()
    if normalized == "RETRIEVER" or documents:
        return "retrieval"
    if normalized == "TOOL":
        return "tool_result"
    if normalized in {"LLM", "CHAIN", "AGENT"}:
        return "llm_call" if normalized == "LLM" else "planner_step"
    return "planner_step"


def _phoenix_documents(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    value = (
        _nested_get(attrs, ["retrieval", "documents"])
        or _nested_get(attrs, ["retrieval.documents"])
        or attrs.get("retrieval.documents")
    )
    return value if isinstance(value, list) else []


def _flatten_document(document: dict[str, Any]) -> dict[str, Any]:
    if isinstance(document.get("document"), dict):
        return {f"document.{key}": value for key, value in document["document"].items()}
    return document


def _nested_get(data: dict[str, Any], path: list[str]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _metadata(attrs: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in attrs.items()
        if key not in {"input", "output", "retrieval", "origo", "input.value", "output.value", "retrieval.documents", "origo.final_output"}
    }
