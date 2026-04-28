from __future__ import annotations

from collections import deque
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


NodeKind = Literal["span", "claim", "action", "evidence", "artifact", "failure_assertion"]

EdgeKind = Literal[
    "parent_child_span",
    "control_flow_next",
    "included_in_prompt",
    "retrieved_for",
    "reranked_into",
    "summarized_into",
    "generated_from",
    "tool_arg_from",
    "tool_output_to_state",
    "memory_overrode",
    "validated_by",
    "failed_to_validate",
    "supports_claim",
    "contradicts_claim",
    "cited_by_output",
    "omitted_from_final_prompt",
    "ignored_by_final_output",
]


class TraceNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: NodeKind
    span_id: str | None = None
    label: str
    content: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    kind: EdgeKind
    confidence: float = 1.0
    evidence: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[TraceNode] = Field(default_factory=list)
    edges: list[TraceEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_edges_reference_nodes(self) -> "TraceGraph":
        ids = {node.id for node in self.nodes}
        for edge in self.edges:
            if edge.source not in ids:
                raise ValueError(f"Edge source '{edge.source}' is not a graph node")
            if edge.target not in ids:
                raise ValueError(f"Edge target '{edge.target}' is not a graph node")
        return self

    def node(self, node_id: str) -> TraceNode:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(node_id)

    def outgoing(self, node_id: str) -> list[TraceEdge]:
        return [edge for edge in self.edges if edge.source == node_id]

    def incoming(self, node_id: str) -> list[TraceEdge]:
        return [edge for edge in self.edges if edge.target == node_id]

    def has_path(self, source: str, target: str, kinds: set[EdgeKind] | None = None) -> bool:
        return self.shortest_path(source, target, kinds) is not None

    def shortest_path(
        self, source: str, target: str, kinds: set[EdgeKind] | None = None
    ) -> list[str] | None:
        if source == target:
            return [source]
        queue: deque[tuple[str, list[str]]] = deque([(source, [source])])
        visited = {source}
        while queue:
            current, path = queue.popleft()
            for edge in self.outgoing(current):
                if kinds is not None and edge.kind not in kinds:
                    continue
                if edge.target in visited:
                    continue
                next_path = [*path, edge.target]
                if edge.target == target:
                    return next_path
                visited.add(edge.target)
                queue.append((edge.target, next_path))
        return None
