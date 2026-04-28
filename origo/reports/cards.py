from __future__ import annotations

from origo.analysis.evidence_matcher import EvidenceMatches, SpanEvidenceMatch, match_evidence
from origo.analysis.ranker import rank_culprits
from origo.graph.builder import build_trace_graph
from origo.graph.omission_edges import add_omission_edges
from origo.schema.failure import FailureSpec
from origo.schema.graph import TraceGraph
from origo.schema.report import CulpritCard, IgnoredEvidence, TracebackReport
from origo.schema.trace import TraceRun, TraceSpan


def analyze_traceback(trace: TraceRun, failure: FailureSpec) -> TracebackReport:
    graph = build_trace_graph(trace, failure)
    matches = match_evidence(trace, failure)
    graph = add_omission_edges(graph, trace, failure, matches)
    candidates = rank_culprits(graph, trace, failure, matches)

    cards = []
    for candidate in candidates[:5]:
        span = trace.get_span(candidate.span_id)
        cards.append(
            CulpritCard(
                title=_title_for(span, failure),
                confidence=min(0.99, round(candidate.score, 2)),
                culprit_span_id=span.id,
                culprit_snippet=_snippet(span),
                path=candidate.path,
                ignored_evidence_span_ids=candidate.ignored_evidence_span_ids,
                ignored_evidence=_ignored_evidence(graph, trace, matches, candidate.ignored_evidence_span_ids),
                failure_modes=candidate.failure_modes,
                suggested_fixes=_suggested_fixes(failure),
                why_suspicious=candidate.reasons,
            )
        )

    return TracebackReport(
        failure_id=failure.failure_id,
        bad_output=failure.bad_output,
        expected=failure.expected,
        cards=cards,
        graph=graph,
    )


def _title_for(span: TraceSpan, failure: FailureSpec) -> str:
    if failure.failure_type == "stale_retrieval" and span.kind == "retrieved_chunk":
        return "Stale policy chunk influenced the final answer"
    if failure.failure_type == "ignored_tool_output":
        return "Correct tool output was ignored by the final answer"
    return f"{span.kind.replace('_', ' ').title()} influenced the final answer"


def _snippet(span: TraceSpan) -> str:
    if span.output is not None:
        return _stringify(span.output)
    if span.input is not None:
        return _stringify(span.input)
    return ""


def _ignored_evidence(
    graph: TraceGraph,
    trace: TraceRun,
    matches: EvidenceMatches,
    ignored_span_ids: list[str],
) -> list[IgnoredEvidence]:
    result: list[IgnoredEvidence] = []
    expected_by_span = {match.span_id: match for match in matches.expected_output}
    omission_edges = {
        edge.source.removeprefix("span:"): edge
        for edge in graph.edges
        if edge.kind in {"omitted_from_final_prompt", "ignored_by_final_output"}
    }
    for span_id in ignored_span_ids:
        span = trace.get_span(span_id)
        match = expected_by_span.get(span_id)
        edge = omission_edges.get(span_id)
        snippet = _snippet(span) if isinstance(span.output, dict) else _match_snippet(match) or _snippet(span)
        result.append(
            IgnoredEvidence(
                span_id=span_id,
                snippet=snippet,
                issue=str(edge.metadata.get("issue")) if edge is not None else "Correct evidence was not reflected in the final output.",
                edge_kind=edge.kind if edge is not None else "ignored_by_final_output",
            )
        )
    return result


def _match_snippet(match: SpanEvidenceMatch | None) -> str:
    if match is None or not match.snippets:
        return ""
    for snippet in match.snippets:
        if any(value in snippet for value in match.matched_values):
            return snippet
    return match.snippets[0]


def _suggested_fixes(failure: FailureSpec) -> list[str]:
    if failure.failure_type == "stale_retrieval":
        return [
            "Prefer current policy tool output over stale retrieved docs.",
            "Add a verifier that checks final claims against the freshest source.",
        ]
    if failure.failure_type == "ignored_tool_output":
        return [
            "Require final synthesis to include relevant tool results.",
            "Add a conflict check before answering when tool output disagrees with the draft answer.",
        ]
    return ["Add an invariant or verifier for this failure mode."]


def _stringify(value: object) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}={_stringify(child)}" for key, child in value.items())
    if isinstance(value, list):
        return ", ".join(_stringify(child) for child in value)
    return str(value)
