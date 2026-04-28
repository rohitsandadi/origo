from __future__ import annotations

from origo.graph.omission_edges import INFORMATION_FLOW_EDGE_KINDS
from origo.schema.failure import FailureSpec
from origo.schema.graph import TraceGraph
from origo.schema.trace import TraceRun


def minimal_traceback_path(graph: TraceGraph, trace: TraceRun, failure: FailureSpec, span_id: str) -> list[str]:
    final_span_id = failure.final_output_span_id
    if final_span_id is None:
        final_span = trace.final_output_span()
        final_span_id = final_span.id if final_span is not None else None
    if final_span_id is None:
        return [span_id]

    path = graph.shortest_path(f"span:{span_id}", f"span:{final_span_id}", kinds=INFORMATION_FLOW_EDGE_KINDS)
    if path is None:
        return [span_id]
    return [node_id.removeprefix("span:") for node_id in path if node_id.startswith("span:")]
