from tests.test_omission_detection import stale_policy_failure, stale_policy_trace

from origo.analysis.evidence_matcher import match_evidence
from origo.analysis.ranker import rank_culprits
from origo.graph.builder import build_trace_graph
from origo.graph.omission_edges import add_omission_edges


def test_ranker_exposes_transparent_reason_codes():
    trace = stale_policy_trace()
    failure = stale_policy_failure()
    graph = build_trace_graph(trace, failure)
    matches = match_evidence(trace, failure)
    graph = add_omission_edges(graph, trace, failure, matches)

    ranked = rank_culprits(graph, trace, failure, matches)

    assert ranked[0].score > 0
    assert "supports bad output" in ranked[0].reasons
    assert "on path to final output" in ranked[0].reasons
    assert "contradicted by omitted expected evidence" in ranked[0].reasons


def test_ranker_does_not_treat_ignored_correct_evidence_as_culprit():
    trace = stale_policy_trace()
    failure = stale_policy_failure()
    graph = build_trace_graph(trace, failure)
    matches = match_evidence(trace, failure)
    graph = add_omission_edges(graph, trace, failure, matches)

    ranked = rank_culprits(graph, trace, failure, matches)

    assert "current_policy_tool" not in [candidate.span_id for candidate in ranked]
