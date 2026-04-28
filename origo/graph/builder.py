from __future__ import annotations

from origo.extraction.claims import extract_bad_output_claim
from origo.graph.deterministic_edges import build_deterministic_edges
from origo.schema.failure import FailureSpec
from origo.schema.graph import TraceEdge, TraceGraph, TraceNode
from origo.schema.trace import TraceRun, TraceSpan


def build_trace_graph(trace: TraceRun, failure: FailureSpec) -> TraceGraph:
    nodes = [_span_node(span) for span in trace.spans]

    claim = extract_bad_output_claim(trace, failure)
    nodes.append(
        TraceNode(
            id=claim.id,
            kind="claim",
            span_id=claim.source_span_id,
            label="Bad output claim",
            content=claim.text,
            metadata=claim.model_dump(exclude={"id", "text"}),
        )
    )
    nodes.append(
        TraceNode(
            id=f"failure:{failure.failure_id}",
            kind="failure_assertion",
            label=failure.failure_id,
            content={
                "bad_output": failure.bad_output,
                "expected": failure.expected,
                "failure_type": failure.failure_type,
                "notes": failure.notes,
            },
        )
    )

    edges = build_deterministic_edges(trace)
    if claim.source_span_id:
        edges.append(
            TraceEdge(
                source=f"span:{claim.source_span_id}",
                target=claim.id,
                kind="generated_from",
                evidence=["final output produced bad output claim"],
            )
        )
    edges.append(
        TraceEdge(
            source=claim.id,
            target=f"failure:{failure.failure_id}",
            kind="contradicts_claim",
            evidence=["failure assertion identifies this output as bad"],
        )
    )

    return TraceGraph(nodes=nodes, edges=_dedupe_edges(edges))


def _span_node(span: TraceSpan) -> TraceNode:
    label = span.name or span.id
    return TraceNode(
        id=f"span:{span.id}",
        kind="span",
        span_id=span.id,
        label=label,
        content={"input": span.input, "output": span.output},
        metadata={"kind": span.kind, **span.metadata},
    )


def _dedupe_edges(edges: list[TraceEdge]) -> list[TraceEdge]:
    deduped: list[TraceEdge] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in edges:
        key = (edge.source, edge.target, edge.kind)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(edge)
    return deduped
