from pathlib import Path

from origo.importers.local_json import load_failure_yaml, load_trace_json
from origo.schema.failure import FailureSpec
from origo.schema.trace import TraceRun


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_loads_rag_stale_policy_trace_json():
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")

    assert isinstance(trace, TraceRun)
    assert trace.run_id == "rag-stale-policy"
    assert trace.final_output_span_id == "final"
    assert trace.span_ids == {
        "user",
        "retrieval_query",
        "policy_old",
        "current_policy_tool",
        "summary",
        "final",
    }
    assert trace.get_span("current_policy_tool").kind == "tool_result"
    assert "90 days" in trace.get_span("final").output


def test_loads_rag_stale_policy_failure_yaml():
    failure = load_failure_yaml(EXAMPLES_DIR / "rag_stale_policy" / "failure.yaml")

    assert isinstance(failure, FailureSpec)
    assert failure.failure_id == "rag-stale-policy"
    assert failure.final_output_span_id == "final"
    assert failure.failure_type == "stale_retrieval"
    assert "current_policy_tool" in failure.expected_evidence_span_ids
    assert "30 days" in failure.expected


def test_loads_ignored_tool_output_trace_json():
    trace = load_trace_json(EXAMPLES_DIR / "ignored_tool_output" / "trace.json")

    assert isinstance(trace, TraceRun)
    assert trace.run_id == "ignored-tool-output"
    assert trace.final_output_span_id == "final"
    assert trace.get_span("tool_result").output["status"] == "eligible"
    assert "eligible" not in trace.get_span("final").output.lower()


def test_loads_ignored_tool_output_failure_yaml():
    failure = load_failure_yaml(EXAMPLES_DIR / "ignored_tool_output" / "failure.yaml")

    assert isinstance(failure, FailureSpec)
    assert failure.failure_id == "ignored-tool-output"
    assert failure.failure_type == "ignored_tool_output"
    assert failure.expected_evidence_span_ids == ["tool_result"]
    assert "eligible" in failure.expected
