from __future__ import annotations

from origo.analysis.candidates import CulpritCandidate
from origo.analysis.evidence_matcher import EvidenceMatches
from origo.analysis.minimal_subgraph import minimal_traceback_path
from origo.graph.omission_edges import INFORMATION_FLOW_EDGE_KINDS
from origo.schema.failure import FailureSpec
from origo.schema.graph import TraceGraph
from origo.schema.trace import TraceRun, TraceSpan


PRIMARY_CULPRIT_KINDS = {
    "retrieved_chunk",
    "context_summary",
    "tool_call",
    "tool_result",
    "memory_read",
    "planner_step",
    "router_decision",
    "validator",
    "parser",
    "state_update",
    "prompt_assembly",
}


def rank_culprits(
    graph: TraceGraph,
    trace: TraceRun,
    failure: FailureSpec,
    matches: EvidenceMatches,
) -> list[CulpritCandidate]:
    final_span_id = _final_span_id(trace, failure)
    bad_match_ids = {match.span_id for match in matches.bad_output}
    expected_match_ids = {match.span_id for match in matches.expected_output}
    ignored_evidence_ids = _ignored_evidence_span_ids(graph)
    omitted_or_ignored = bool(ignored_evidence_ids)

    candidates: list[CulpritCandidate] = []
    for span in trace.spans:
        if span.id == final_span_id or span.kind not in PRIMARY_CULPRIT_KINDS:
            continue
        if span.id in expected_match_ids and span.id not in bad_match_ids:
            continue

        score = 0.0
        reasons: list[str] = []
        failure_modes: list[str] = []

        if span.id in bad_match_ids:
            score += 0.25
            reasons.append("supports bad output")

        on_path = bool(final_span_id and graph.has_path(
            f"span:{span.id}",
            f"span:{final_span_id}",
            kinds=INFORMATION_FLOW_EDGE_KINDS,
        ))
        if on_path:
            score += 0.20
            reasons.append("on path to final output")

        if span.id in bad_match_ids and expected_match_ids:
            score += 0.20
            reasons.append("contradicted by omitted expected evidence")

        if omitted_or_ignored and (span.id in bad_match_ids or on_path):
            score += 0.15
            reasons.append("omission or ignored-evidence signal present")
            failure_modes.append("ignored_tool_output")

        if failure.failure_type:
            failure_modes.append(failure.failure_type)
            if failure.failure_type == "stale_retrieval" and span.kind == "retrieved_chunk":
                score += 0.10
                reasons.append("retrieved chunk in stale-retrieval failure")

        if _is_stale(span):
            score += 0.05
            reasons.append("stale metadata signal")

        if score == 0:
            continue

        candidates.append(
            CulpritCandidate(
                span_id=span.id,
                score=round(score, 4),
                reasons=_unique(reasons),
                ignored_evidence_span_ids=ignored_evidence_ids if (span.id in bad_match_ids or on_path) else [],
                failure_modes=_unique(failure_modes),
                path=minimal_traceback_path(graph, trace, failure, span.id),
            )
        )

    return sorted(candidates, key=lambda candidate: (-candidate.score, _kind_priority(trace, candidate.span_id), candidate.span_id))


def _final_span_id(trace: TraceRun, failure: FailureSpec) -> str | None:
    if failure.final_output_span_id:
        return failure.final_output_span_id
    final_span = trace.final_output_span()
    return final_span.id if final_span else None


def _ignored_evidence_span_ids(graph: TraceGraph) -> list[str]:
    ids: list[str] = []
    for edge in graph.edges:
        if edge.kind not in {"omitted_from_final_prompt", "ignored_by_final_output"}:
            continue
        span_id = edge.source.removeprefix("span:")
        if span_id not in ids:
            ids.append(span_id)
    return ids


def _is_stale(span: TraceSpan) -> bool:
    date = span.metadata.get("date")
    return isinstance(date, str) and date < "2025"


def _kind_priority(trace: TraceRun, span_id: str) -> int:
    priority = {
        "retrieved_chunk": 0,
        "tool_call": 1,
        "memory_read": 2,
        "context_summary": 3,
        "tool_result": 4,
        "planner_step": 5,
        "router_decision": 6,
        "validator": 7,
    }
    try:
        return priority.get(trace.get_span(span_id).kind, 99)
    except KeyError:
        return 99


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
