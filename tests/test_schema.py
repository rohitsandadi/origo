import pytest
from pydantic import ValidationError

from origo.schema.failure import FailureSpec
from origo.schema.graph import TraceEdge, TraceGraph, TraceNode
from origo.schema.report import CulpritCard, TracebackReport
from origo.schema.trace import TraceRun, TraceSpan


def test_trace_run_accepts_valid_trace():
    trace = TraceRun(
        run_id="refund-demo",
        task="Answer a refund question.",
        spans=[
            TraceSpan(id="user", kind="user_input", output="Can I get a refund?"),
            TraceSpan(id="final", parent_id="user", kind="final_output", output="Yes."),
        ],
        final_output_span_id="final",
    )

    assert trace.span_ids == {"user", "final"}
    assert trace.get_span("final").kind == "final_output"


def test_trace_run_rejects_duplicate_span_ids():
    with pytest.raises(ValidationError, match="Duplicate span id"):
        TraceRun(
            run_id="bad",
            spans=[
                TraceSpan(id="same", kind="user_input"),
                TraceSpan(id="same", kind="final_output"),
            ],
        )


def test_trace_run_rejects_unknown_parent_id():
    with pytest.raises(ValidationError, match="Unknown parent_id"):
        TraceRun(
            run_id="bad",
            spans=[
                TraceSpan(id="child", parent_id="missing", kind="final_output"),
            ],
        )


def test_trace_run_rejects_unknown_final_output_span_id():
    with pytest.raises(ValidationError, match="Unknown final_output_span_id"):
        TraceRun(
            run_id="bad",
            spans=[TraceSpan(id="user", kind="user_input")],
            final_output_span_id="missing",
        )


def test_failure_spec_uses_origo_failure_modes():
    spec = FailureSpec(
        failure_id="refund_window_wrong",
        bad_output="refund window is 90 days",
        expected="refund window is 30 days",
        failure_type="stale_retrieval",
        expected_evidence_span_ids=["current_policy_tool"],
    )

    assert spec.failure_type == "stale_retrieval"


def test_graph_and_report_schemas_capture_span_evidence():
    graph = TraceGraph(
        nodes=[
            TraceNode(id="span:policy_old", kind="span", span_id="policy_old", label="policy_old"),
            TraceNode(id="claim:bad", kind="claim", span_id="final", label="Bad claim"),
        ],
        edges=[
            TraceEdge(
                source="span:policy_old",
                target="claim:bad",
                kind="supports_claim",
                evidence=["Refunds are allowed within 90 days."],
            )
        ],
    )
    report = TracebackReport(
        failure_id="refund_window_wrong",
        bad_output="refund window is 90 days",
        expected="refund window is 30 days",
        cards=[
            CulpritCard(
                title="Stale policy chunk influenced the final answer",
                confidence=0.86,
                culprit_span_id="policy_old",
                culprit_snippet="Refunds are allowed within 90 days.",
                path=["policy_old", "summary", "final"],
                ignored_evidence_span_ids=["current_policy_tool"],
                failure_modes=["stale_retrieval", "ignored_tool_output"],
                suggested_fixes=["Prefer current policy tool output over stale retrieved docs."],
            )
        ],
        graph=graph,
    )

    assert report.cards[0].culprit_span_id == "policy_old"
    assert report.graph.edges[0].kind == "supports_claim"
