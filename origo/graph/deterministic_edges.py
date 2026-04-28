from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from origo.schema.graph import TraceEdge
from origo.schema.trace import TraceRun, TraceSpan


def build_deterministic_edges(trace: TraceRun) -> list[TraceEdge]:
    spans_by_id = {span.id: span for span in trace.spans}
    edges: list[TraceEdge] = []
    seen: set[tuple[str, str, str]] = set()

    def add(source_span_id: str, target_span_id: str, kind: str, evidence: Iterable[str] = ()) -> None:
        if source_span_id not in spans_by_id or target_span_id not in spans_by_id:
            return
        key = (source_span_id, target_span_id, kind)
        if key in seen:
            return
        seen.add(key)
        edges.append(
            TraceEdge(
                source=f"span:{source_span_id}",
                target=f"span:{target_span_id}",
                kind=kind,  # type: ignore[arg-type]
                evidence=list(evidence),
            )
        )

    for span in trace.spans:
        if span.parent_id is not None:
            add(span.parent_id, span.id, "parent_child_span")

    for retrieval in trace.spans:
        if retrieval.kind != "retrieval":
            continue
        for chunk_id in _referenced_span_ids(retrieval.output, keys=("chunk_id", "chunk_ids", "span_id", "span_ids")):
            add(retrieval.id, chunk_id, "retrieved_for", evidence=["retrieval output references chunk"])
        for chunk in trace.spans:
            if chunk.kind == "retrieved_chunk" and chunk.parent_id == retrieval.id:
                add(retrieval.id, chunk.id, "retrieved_for", evidence=["chunk parent is retrieval"])

    for summary in trace.spans:
        if summary.kind != "context_summary":
            continue
        for source_id in _summary_source_ids(summary, trace):
            source = spans_by_id.get(source_id)
            kind = "tool_output_to_state" if source is not None and source.kind == "tool_result" else "summarized_into"
            add(source_id, summary.id, kind, evidence=["summary input references source"])

    for final in trace.spans:
        if final.kind != "final_output":
            continue
        for source_id in _final_source_ids(final, trace):
            add(source_id, final.id, "generated_from", evidence=["final input references source"])
        for tool_result_id in _referenced_span_ids(
            final.input,
            keys=("tool_result_span_id", "tool_result_span_ids", "available_tool_result_span_ids"),
        ):
            add(tool_result_id, final.id, "tool_output_to_state", evidence=["tool result available to final output"])

    return edges


def _summary_source_ids(summary: TraceSpan, trace: TraceRun) -> set[str]:
    source_ids = set(
        _referenced_span_ids(
            summary.input,
            keys=(
                "source_span_id",
                "source_span_ids",
                "chunk_id",
                "chunk_ids",
                "retrieved_span_id",
                "retrieved_span_ids",
                "tool_result_span_id",
                "tool_result_span_ids",
                "span_id",
                "span_ids",
            ),
        )
    )
    if isinstance(summary.input, str) and summary.input in trace.span_ids:
        source_ids.add(summary.input)
    if summary.parent_id is not None:
        parent = trace.get_span(summary.parent_id)
        if parent.kind == "retrieval":
            source_ids.update(
                _referenced_span_ids(parent.output, keys=("chunk_id", "chunk_ids", "span_id", "span_ids"))
            )
            source_ids.update(span.id for span in trace.spans if span.parent_id == parent.id and span.kind == "retrieved_chunk")
        elif parent.kind in {"retrieved_chunk", "tool_result", "memory_read", "state_update", "prompt_assembly"}:
            source_ids.add(parent.id)
    return source_ids


def _final_source_ids(final: TraceSpan, trace: TraceRun) -> set[str]:
    source_ids = set(
        _referenced_span_ids(
            final.input,
            keys=(
                "summary_span_id",
                "summary_span_ids",
                "source_span_id",
                "source_span_ids",
                "generated_from_span_id",
                "generated_from_span_ids",
                "span_id",
                "span_ids",
            ),
        )
    )
    if isinstance(final.input, str) and final.input in trace.span_ids:
        source_ids.add(final.input)
    if final.parent_id is not None:
        parent = trace.get_span(final.parent_id)
        if parent.kind in {"context_summary", "prompt_assembly", "llm_call", "tool_result", "state_update"}:
            source_ids.add(parent.id)
    return source_ids


def _referenced_span_ids(value: Any, keys: tuple[str, ...]) -> set[str]:
    found: set[str] = set()

    def visit(current: Any, key: str | None = None) -> None:
        if isinstance(current, dict):
            for child_key, child_value in current.items():
                visit(child_value, str(child_key))
            return
        if isinstance(current, list | tuple | set):
            for item in current:
                visit(item, key)
            return
        if key in keys and isinstance(current, str):
            found.add(current)

    visit(value)
    return found
