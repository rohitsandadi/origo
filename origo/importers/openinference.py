from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from origo.schema.trace import TraceRun, TraceSpan


def load_openinference_json(path: str | Path) -> TraceRun:
    """Load an OTLP/OpenInference JSON trace into Origo's local trace schema."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return openinference_json_to_trace(data)


def openinference_json_to_trace(data: dict[str, Any]) -> TraceRun:
    spans: list[TraceSpan] = []
    trace_ids: set[str] = set()
    explicit_final_span_id: str | None = None

    for otel_span in _iter_otel_spans(data):
        trace_id = _decode_id(otel_span.get("traceId"))
        span_id = _decode_id(otel_span.get("spanId"))
        if trace_id is None or span_id is None:
            raise ValueError("OTLP span is missing traceId or spanId")
        trace_ids.add(trace_id)

        parent_id = _decode_id(otel_span.get("parentSpanId"))
        attrs = _attributes_to_dict(otel_span.get("attributes", []))
        documents = _coerce_documents(attrs.get("retrieval.documents"))
        is_final = bool(attrs.get("origo.final_output"))
        kind = _span_kind(attrs, documents, is_final)
        if is_final:
            explicit_final_span_id = span_id

        span_output = [f"{span_id}.document.{index}" for index, _ in enumerate(documents)] if documents else _value_attr(attrs, "output.value")
        spans.append(
            TraceSpan(
                id=span_id,
                parent_id=parent_id,
                kind=kind,
                name=otel_span.get("name"),
                input=_value_attr(attrs, "input.value"),
                output=span_output,
                metadata=_metadata(attrs),
                started_at=_nanos_to_seconds(otel_span.get("startTimeUnixNano")),
                ended_at=_nanos_to_seconds(otel_span.get("endTimeUnixNano")),
            )
        )

        for index, document in enumerate(documents):
            document_span_id = f"{span_id}.document.{index}"
            spans.append(
                TraceSpan(
                    id=document_span_id,
                    parent_id=span_id,
                    kind="retrieved_chunk",
                    name=str(document.get("document.id") or f"retrieved document {index}"),
                    output=_document_content(document),
                    metadata={key: value for key, value in document.items() if key != "document.content"},
                    started_at=_nanos_to_seconds(otel_span.get("startTimeUnixNano")),
                    ended_at=_nanos_to_seconds(otel_span.get("endTimeUnixNano")),
                )
            )

    if not spans:
        raise ValueError("No OTLP spans found")
    if len(trace_ids) != 1:
        raise ValueError("OpenInference importer currently expects exactly one trace")

    final_output_span_id = explicit_final_span_id or _infer_final_output_span_id(spans)
    return TraceRun(
        run_id=next(iter(trace_ids)),
        spans=spans,
        final_output_span_id=final_output_span_id,
        metadata={"source_schema": "openinference.otlp_json"},
    )


def _iter_otel_spans(data: dict[str, Any]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for resource_span in data.get("resourceSpans", []):
        for scope_span in resource_span.get("scopeSpans", []):
            spans.extend(scope_span.get("spans", []))
    return spans


def _decode_id(value: Any) -> str | None:
    if not value:
        return None
    if not isinstance(value, str):
        return str(value)
    lowered = value.lower()
    if len(lowered) in {16, 32} and all(char in "0123456789abcdef" for char in lowered):
        return lowered
    try:
        decoded = base64.b64decode(value, validate=True)
    except Exception:
        return value
    if len(decoded) in {8, 16}:
        return decoded.hex()
    return value


def _attributes_to_dict(attributes: list[dict[str, Any]]) -> dict[str, Any]:
    return {attr.get("key", ""): _decode_value(attr.get("value", {})) for attr in attributes}


def _decode_value(value: dict[str, Any]) -> Any:
    if "stringValue" in value:
        return _maybe_json(value["stringValue"])
    if "boolValue" in value:
        return value["boolValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return value["doubleValue"]
    if "arrayValue" in value:
        return [_decode_value(child) for child in value["arrayValue"].get("values", [])]
    if "kvlistValue" in value:
        return {
            item.get("key", ""): _decode_value(item.get("value", {}))
            for item in value["kvlistValue"].get("values", [])
        }
    return None


def _maybe_json(value: str) -> Any:
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _coerce_documents(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, str):
        value = _maybe_json(value)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _span_kind(attrs: dict[str, Any], documents: list[dict[str, Any]], is_final: bool) -> str:
    if is_final:
        return "final_output"
    openinference_kind = str(attrs.get("openinference.span.kind") or "").upper()
    if openinference_kind == "RETRIEVER" or documents:
        return "retrieval"
    if openinference_kind == "TOOL":
        return "tool_result" if attrs.get("output.value") is not None else "tool_call"
    if openinference_kind == "LLM":
        return "llm_call"
    if openinference_kind in {"AGENT", "CHAIN"}:
        return "planner_step"
    return "llm_call" if attrs.get("output.value") is not None else "planner_step"


def _value_attr(attrs: dict[str, Any], key: str) -> Any:
    return attrs.get(key)


def _metadata(attrs: dict[str, Any]) -> dict[str, Any]:
    excluded = {
        "input.value",
        "output.value",
        "retrieval.documents",
        "openinference.span.kind",
        "origo.final_output",
    }
    return {key: value for key, value in attrs.items() if key not in excluded}


def _document_content(document: dict[str, Any]) -> Any:
    return document.get("document.content") or document.get("content") or document


def _nanos_to_seconds(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return int(value) / 1_000_000_000


def _infer_final_output_span_id(spans: list[TraceSpan]) -> str | None:
    for span in reversed(spans):
        if span.kind in {"final_output", "llm_call"} and span.output is not None:
            return span.id
    return None
