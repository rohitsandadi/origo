import json

from origo.pipeline import analyze_with_artifacts
from origo.schema.failure import FailureSpec
from origo.schema.trace import TraceRun, TraceSpan


def test_wrong_tool_argument_check_fails_when_tool_args_conflict_with_user_request(tmp_path):
    trace = TraceRun(
        run_id="wrong-tool-argument",
        spans=[
            TraceSpan(
                id="user",
                kind="user_input",
                output={"intent": "refund_status", "order_id": "A100"},
            ),
            TraceSpan(
                id="lookup_call",
                parent_id="user",
                kind="tool_call",
                output={"tool_name": "refund_status", "arguments": {"order_id": "B200"}},
            ),
            TraceSpan(
                id="lookup_result",
                parent_id="lookup_call",
                kind="tool_result",
                output={"order_id": "B200", "status": "ineligible"},
            ),
            TraceSpan(
                id="final",
                parent_id="lookup_result",
                kind="final_output",
                input={"context_span_ids": ["lookup_result"]},
                output="Order B200 is not eligible for refund.",
            ),
        ],
        final_output_span_id="final",
    )
    failure = FailureSpec(
        failure_id="wrong-tool-argument",
        bad_output="Order B200 is not eligible for refund.",
        expected="Look up order A100.",
        failure_type="wrong_tool_argument",
    )

    analyze_with_artifacts(trace, failure, run_root=tmp_path)

    validation_log = json.loads((tmp_path / "wrong-tool-argument" / "validation_log.json").read_text())
    wrong_arg_check = next(
        check for check in validation_log if check["id"] == "check:wrong_tool_argument:lookup_call.output"
    )

    assert wrong_arg_check["status"] == "fail"
    assert wrong_arg_check["invariant_id"] == "builtin:wrong_tool_argument"
    assert wrong_arg_check["target_artifact_id"] == "lookup_call.output"
    assert wrong_arg_check["evidence_refs"] == ["lookup_call.output", "user.output"]
    assert "order_id" in wrong_arg_check["explanation"]


def test_wrong_tool_argument_check_does_not_fail_when_shared_fields_match(tmp_path):
    trace = TraceRun(
        run_id="correct-tool-argument",
        spans=[
            TraceSpan(id="user", kind="user_input", output={"order_id": "A100"}),
            TraceSpan(
                id="lookup_call",
                parent_id="user",
                kind="tool_call",
                output={"tool_name": "refund_status", "arguments": {"order_id": "A100"}},
            ),
            TraceSpan(id="final", parent_id="lookup_call", kind="final_output", output="Order A100 is eligible."),
        ],
        final_output_span_id="final",
    )
    failure = FailureSpec(
        failure_id="correct-tool-argument",
        bad_output="Order A100 is eligible.",
        failure_type="wrong_tool_argument",
    )

    analyze_with_artifacts(trace, failure, run_root=tmp_path)

    validation_log = json.loads((tmp_path / "correct-tool-argument" / "validation_log.json").read_text())

    assert "check:wrong_tool_argument:lookup_call.output" not in {check["id"] for check in validation_log}
