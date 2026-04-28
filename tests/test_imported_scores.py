import json

from origo.importers.langfuse import load_langfuse_json
from origo.pipeline import analyze_with_artifacts
from origo.schema.failure import FailureSpec


def test_langfuse_observation_scores_become_validation_checks(tmp_path):
    payload = {
        "trace": {
            "id": "trace-1",
            "input": "Can order A100 be refunded?",
            "output": "Order A100 cannot be refunded.",
        },
        "observations": [
            {
                "id": "tool-result",
                "traceId": "trace-1",
                "type": "TOOL",
                "output": {"status": "eligible"},
            },
            {
                "id": "final",
                "traceId": "trace-1",
                "parentObservationId": "tool-result",
                "type": "GENERATION",
                "output": "Order A100 cannot be refunded.",
            },
        ],
        "scores": [
            {
                "id": "score-1",
                "name": "tool_response_handling",
                "value": 0,
                "observationId": "final",
                "comment": "The final answer ignored the eligible tool result.",
            }
        ],
    }
    trace_path = tmp_path / "langfuse.json"
    trace_path.write_text(json.dumps(payload), encoding="utf-8")
    trace = load_langfuse_json(trace_path)
    failure = FailureSpec(
        failure_id="refund-ignored",
        final_output_span_id="final",
        bad_output="Order A100 cannot be refunded.",
        expected="Order A100 is eligible for a refund.",
        failure_type="ignored_tool_output",
        expected_evidence_span_ids=["tool-result"],
    )

    result = analyze_with_artifacts(trace, failure, run_root=tmp_path)

    imported_checks = [check for check in result.validation_log if check.id == "imported-score:score-1"]
    assert len(imported_checks) == 1
    assert imported_checks[0].status == "fail"
    assert imported_checks[0].failure_mode == "ignored_tool_output"
    assert imported_checks[0].target_artifact_id == "final.output"
    assert imported_checks[0].checker_kind == "deterministic"
