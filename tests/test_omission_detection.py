from origo.analysis.evidence_matcher import match_evidence
from origo.analysis.ranker import rank_culprits
from origo.graph.builder import build_trace_graph
from origo.graph.omission_edges import add_omission_edges
from origo.schema.failure import FailureSpec
from origo.schema.trace import TraceRun, TraceSpan


def stale_policy_trace() -> TraceRun:
    return TraceRun(
        run_id="refund-demo-001",
        task="Answer whether customer is eligible for refund.",
        spans=[
            TraceSpan(
                id="user",
                kind="user_input",
                output="Customer purchased 45 days ago. Are they eligible for a refund?",
                started_at=1,
            ),
            TraceSpan(
                id="retrieval_query",
                parent_id="user",
                kind="retrieval",
                input="refund policy window",
                output=["policy_old"],
                started_at=2,
            ),
            TraceSpan(
                id="policy_old",
                parent_id="retrieval_query",
                kind="retrieved_chunk",
                output="Refunds are allowed within 90 days.",
                metadata={"date": "2024-02-12"},
                started_at=3,
            ),
            TraceSpan(
                id="current_policy_tool",
                parent_id="user",
                kind="tool_result",
                output={"refund_window_days": 30},
                metadata={"date": "2026-04-28"},
                started_at=4,
            ),
            TraceSpan(
                id="summary",
                parent_id="policy_old",
                kind="context_summary",
                input="policy_old",
                output="Refunds are allowed within 90 days.",
                started_at=5,
            ),
            TraceSpan(
                id="final",
                parent_id="summary",
                kind="final_output",
                input="summary",
                output="The customer is eligible because refunds are allowed within 90 days.",
                started_at=6,
            ),
        ],
        final_output_span_id="final",
    )


def stale_policy_failure() -> FailureSpec:
    return FailureSpec(
        failure_id="refund_window_wrong",
        bad_output="refunds are allowed within 90 days",
        expected="refunds are allowed within 30 days",
        failure_type="stale_retrieval",
        expected_evidence_span_ids=["current_policy_tool"],
    )


def test_omission_detection_adds_edge_for_correct_tool_result_missing_from_final_path():
    trace = stale_policy_trace()
    failure = stale_policy_failure()
    graph = build_trace_graph(trace, failure)
    matches = match_evidence(trace, failure)

    graph = add_omission_edges(graph, trace, failure, matches)

    assert any(
        edge.kind == "omitted_from_final_prompt"
        and edge.source == "span:current_policy_tool"
        and edge.target == "span:final"
        for edge in graph.edges
    )


def test_stale_chunk_ranks_top_culprit_and_correct_tool_output_is_ignored_evidence():
    trace = stale_policy_trace()
    failure = stale_policy_failure()
    graph = build_trace_graph(trace, failure)
    matches = match_evidence(trace, failure)
    graph = add_omission_edges(graph, trace, failure, matches)

    ranked = rank_culprits(graph, trace, failure, matches)

    assert ranked[0].span_id == "policy_old"
    assert ranked[0].ignored_evidence_span_ids == ["current_policy_tool"]
    assert "stale_retrieval" in ranked[0].failure_modes


def test_expected_evidence_span_ids_are_used_when_expected_text_does_not_match():
    trace = stale_policy_trace()
    failure = FailureSpec(
        failure_id="refund_window_wrong",
        bad_output="refunds are allowed within 90 days",
        expected="The answer should deny the refund.",
        failure_type="stale_retrieval",
        expected_evidence_span_ids=["current_policy_tool"],
    )
    graph = build_trace_graph(trace, failure)
    matches = match_evidence(trace, failure)

    graph = add_omission_edges(graph, trace, failure, matches)

    assert any(
        edge.source == "span:current_policy_tool"
        and edge.target == "span:final"
        and edge.kind in {"omitted_from_final_prompt", "ignored_by_final_output"}
        for edge in graph.edges
    )
