from __future__ import annotations

from origo.ir.models import Artifact, TrajectoryIR
from origo.schema.graph import TraceEdge, TraceGraph, TraceNode


def build_artifact_provenance_graph(ir: TrajectoryIR, artifacts: list[Artifact]) -> TraceGraph:
    """Build a graph over spans and artifact-level evidence units."""

    nodes: list[TraceNode] = []
    edges: list[TraceEdge] = []

    span_node_ids: set[str] = set()
    for step in ir.steps:
        if step.span_id is None:
            continue
        node_id = f"span:{step.span_id}"
        span_node_ids.add(node_id)
        nodes.append(
            TraceNode(
                id=node_id,
                kind="span",
                span_id=step.span_id,
                label=step.name or step.kind,
                content=None,
                metadata={"step_index": step.index, "step_kind": step.kind},
            )
        )

    artifact_node_ids: set[str] = set()
    for artifact in artifacts:
        node_id = f"artifact:{artifact.id}"
        artifact_node_ids.add(node_id)
        nodes.append(
            TraceNode(
                id=node_id,
                kind="artifact",
                span_id=artifact.span_id,
                label=artifact.id,
                content=artifact.text,
                metadata={"artifact_kind": artifact.kind, **artifact.metadata},
            )
        )
        span_node_id = f"span:{artifact.span_id}"
        if artifact.span_id is not None and span_node_id in span_node_ids:
            edges.append(
                TraceEdge(
                    source=span_node_id,
                    target=node_id,
                    kind="contains_artifact",
                    evidence=[artifact.id],
                    metadata={"artifact_kind": artifact.kind},
                )
            )

    for artifact in artifacts:
        target_id = f"artifact:{artifact.id}"
        if target_id not in artifact_node_ids:
            continue
        for input_artifact_id in artifact.metadata.get("input_artifact_ids", []):
            source_id = f"artifact:{input_artifact_id}"
            if source_id not in artifact_node_ids:
                continue
            edges.append(
                TraceEdge(
                    source=source_id,
                    target=target_id,
                    kind="generated_from",
                    evidence=[input_artifact_id, artifact.id],
                    metadata={"method": "trace_input_reference"},
                )
            )

    output_by_span = {
        artifact.span_id: artifact
        for artifact in artifacts
        if artifact.span_id is not None and artifact.id.endswith(".output")
    }
    for step in ir.steps:
        if step.span_id is None or step.parent_span_id is None:
            continue
        source = output_by_span.get(step.parent_span_id)
        target = output_by_span.get(step.span_id)
        if source is None or target is None:
            continue
        if target.metadata.get("input_artifact_ids"):
            continue
        edges.append(
            TraceEdge(
                source=f"artifact:{source.id}",
                target=f"artifact:{target.id}",
                kind="generated_from",
                evidence=[source.id, target.id],
                metadata={"method": "parent_span_output_fallback"},
            )
        )

    return TraceGraph(nodes=nodes, edges=edges)
