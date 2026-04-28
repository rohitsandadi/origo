from __future__ import annotations

from origo.analysis.evidence_matcher import EvidenceMatches
from origo.analysis.evidence_matcher import SpanEvidenceMatch
from origo.schema.failure import FailureSpec
from origo.schema.graph import EdgeKind, TraceEdge, TraceGraph
from origo.schema.trace import TraceRun


INFORMATION_FLOW_EDGE_KINDS: set[EdgeKind] = {
    "included_in_prompt",
    "retrieved_for",
    "reranked_into",
    "summarized_into",
    "generated_from",
    "tool_output_to_state",
    "memory_overrode",
}


def add_omission_edges(
    graph: TraceGraph,
    trace: TraceRun,
    failure: FailureSpec,
    matches: EvidenceMatches,
) -> TraceGraph:
    """Add edges for correct evidence that failed to shape the final output."""
    final_span = _final_span_id(trace, failure)
    if final_span is None:
        return graph

    edges = list(graph.edges)
    seen = {(edge.source, edge.target, edge.kind) for edge in edges}
    bad_span_ids = {match.span_id for match in matches.bad_output}
    expected_matches = {match.span_id: match for match in matches.expected_output}
    for span_id in failure.expected_evidence_span_ids:
        if span_id not in expected_matches and span_id in trace.span_ids:
            span = trace.get_span(span_id)
            expected_matches[span_id] = SpanEvidenceMatch(
                span_id=span_id,
                snippets=[_stringify(span.output if span.output is not None else span.input)],
                matched_fields=["expected_evidence_span_ids"],
            )

    for match in expected_matches.values():
        source = f"span:{match.span_id}"
        target = f"span:{final_span}"
        if source == target:
            continue

        has_path = graph.has_path(source, target, kinds=INFORMATION_FLOW_EDGE_KINDS)
        kind: EdgeKind = "ignored_by_final_output" if has_path and final_span in bad_span_ids else "omitted_from_final_prompt"
        key = (source, target, kind)
        if key in seen:
            continue
        seen.add(key)
        edges.append(
            TraceEdge(
                source=source,
                target=target,
                kind=kind,
                evidence=match.snippets,
                metadata={
                    "matched_values": match.matched_values,
                    "matched_fields": match.matched_fields,
                    "issue": _issue_text(kind),
                },
            )
        )

    return TraceGraph(nodes=graph.nodes, edges=edges)


def _final_span_id(trace: TraceRun, failure: FailureSpec) -> str | None:
    if failure.final_output_span_id:
        return failure.final_output_span_id
    final_span = trace.final_output_span()
    return final_span.id if final_span else None


def _issue_text(kind: EdgeKind) -> str:
    if kind == "ignored_by_final_output":
        return "Correct evidence reached the final context, but the final output contradicted it."
    return "Correct evidence existed before the final output, but no information-flow path reached the final output."


def _stringify(value: object) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}={_stringify(child)}" for key, child in value.items())
    if isinstance(value, list):
        return ", ".join(_stringify(child) for child in value)
    return str(value)
