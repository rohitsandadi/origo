from origo.analysis.evidence_matcher import match_evidence
from origo.extraction.claims import extract_bad_output_claim
from origo.graph.builder import build_trace_graph
from origo.schema.failure import FailureSpec
from origo.schema.trace import TraceRun, TraceSpan


def stale_policy_trace() -> tuple[TraceRun, FailureSpec]:
    trace = TraceRun(
        run_id="stale-policy",
        task="Answer a refund policy question.",
        spans=[
            TraceSpan(
                id="user",
                kind="user_input",
                output="What is the refund window?",
            ),
            TraceSpan(
                id="policy_retrieval",
                parent_id="user",
                kind="retrieval",
                input="refund policy",
                output={"chunk_ids": ["policy_old"]},
            ),
            TraceSpan(
                id="policy_old",
                parent_id="policy_retrieval",
                kind="retrieved_chunk",
                output={
                    "title": "Legacy refund policy",
                    "refund_window_days": 90,
                    "text": "Refunds are available within 90 days of purchase.",
                },
            ),
            TraceSpan(
                id="summary",
                parent_id="policy_retrieval",
                kind="context_summary",
                input={"chunk_ids": ["policy_old"], "tool_result_span_ids": ["current_policy_tool"]},
                output="Summary: refunds are available within 90 days of purchase.",
            ),
            TraceSpan(
                id="current_policy_tool",
                parent_id="user",
                kind="tool_result",
                output={
                    "source": "policy_api",
                    "refund_window_days": 30,
                    "text": "Current policy: refunds are available within 30 days of purchase.",
                },
            ),
            TraceSpan(
                id="final",
                parent_id="summary",
                kind="final_output",
                input={
                    "summary_span_id": "summary",
                    "available_tool_result_span_ids": ["current_policy_tool"],
                },
                output="Refunds are available within 90 days of purchase.",
            ),
        ],
        final_output_span_id="final",
    )
    failure = FailureSpec(
        failure_id="refund-window-stale",
        bad_output="Refunds are available within 90 days of purchase.",
        expected="Refunds are available within 30 days of purchase.",
        failure_type="stale_retrieval",
        expected_evidence_span_ids=["current_policy_tool"],
    )
    return trace, failure


def test_extracts_bad_output_as_single_claim():
    trace, failure = stale_policy_trace()

    claim = extract_bad_output_claim(trace, failure)

    assert claim.id == "claim:bad_output"
    assert claim.text == failure.bad_output
    assert claim.source_span_id == "final"


def test_builds_stale_policy_information_flow_graph():
    trace, failure = stale_policy_trace()

    graph = build_trace_graph(trace, failure)

    assert {node.id for node in graph.nodes} >= {
        "span:policy_old",
        "span:summary",
        "span:final",
        "claim:bad_output",
        "failure:refund-window-stale",
    }
    assert graph.has_path(
        "span:policy_old",
        "span:final",
        kinds={"summarized_into", "generated_from"},
    )
    assert graph.shortest_path(
        "span:policy_old",
        "span:final",
        kinds={"summarized_into", "generated_from"},
    ) == ["span:policy_old", "span:summary", "span:final"]

    edge_facts = {(edge.source, edge.target, edge.kind) for edge in graph.edges}
    assert ("span:policy_retrieval", "span:policy_old", "retrieved_for") in edge_facts
    assert ("span:policy_old", "span:summary", "summarized_into") in edge_facts
    assert ("span:current_policy_tool", "span:summary", "tool_output_to_state") in edge_facts
    assert ("span:summary", "span:final", "generated_from") in edge_facts
    assert ("span:current_policy_tool", "span:final", "tool_output_to_state") in edge_facts
    assert ("span:final", "claim:bad_output", "generated_from") in edge_facts


def test_exact_value_matcher_finds_bad_and_expected_evidence():
    trace, failure = stale_policy_trace()

    matches = match_evidence(trace, failure)

    assert [match.span_id for match in matches.bad_output] == ["policy_old", "summary", "final"]
    assert matches.bad_output[0].matched_values == ["90"]
    assert "Refunds are available within 90 days of purchase." in matches.bad_output[0].snippets
    assert [match.span_id for match in matches.expected_output] == ["current_policy_tool"]
    assert matches.expected_output[0].matched_values == ["30"]
