import json

from origo.pipeline import analyze_with_artifacts
from origo.schema.failure import FailureSpec
from origo.schema.trace import TraceRun, TraceSpan


def test_unsupported_claim_check_fails_when_included_evidence_does_not_support_final_claim(tmp_path):
    trace = TraceRun(
        run_id="unsupported-claim",
        spans=[
            TraceSpan(id="user", kind="user_input", output="How long is the warranty?"),
            TraceSpan(
                id="policy_doc",
                parent_id="user",
                kind="retrieved_chunk",
                output="The warranty lasts 12 months for standard plans.",
            ),
            TraceSpan(
                id="final",
                parent_id="policy_doc",
                kind="final_output",
                input={"context_span_ids": ["policy_doc"]},
                output="The warranty lasts 3 years.",
            ),
        ],
        final_output_span_id="final",
    )
    failure = FailureSpec(
        failure_id="unsupported-claim",
        bad_output="The warranty lasts 3 years.",
        expected="The warranty lasts 12 months for standard plans.",
        failure_type="unsupported_claim",
    )

    analyze_with_artifacts(trace, failure, run_root=tmp_path)

    validation_log = json.loads((tmp_path / "unsupported-claim" / "validation_log.json").read_text())
    unsupported_check = next(
        check for check in validation_log if check["id"] == "check:unsupported_claim:final.output"
    )

    assert unsupported_check["status"] == "fail"
    assert unsupported_check["invariant_id"] == "builtin:unsupported_claim"
    assert unsupported_check["target_artifact_id"] == "final.output"
    assert unsupported_check["evidence_refs"] == ["final.output", "policy_doc.output"]


def test_unsupported_claim_check_passes_when_included_evidence_supports_final_claim(tmp_path):
    trace = TraceRun(
        run_id="supported-claim",
        spans=[
            TraceSpan(
                id="policy_doc",
                kind="retrieved_chunk",
                output="The warranty lasts 3 years for premium plans.",
            ),
            TraceSpan(
                id="final",
                parent_id="policy_doc",
                kind="final_output",
                input={"context_span_ids": ["policy_doc"]},
                output="The warranty lasts 3 years.",
            ),
        ],
        final_output_span_id="final",
    )
    failure = FailureSpec(
        failure_id="supported-claim",
        bad_output="The warranty lasts 3 years.",
        failure_type="unsupported_claim",
    )

    analyze_with_artifacts(trace, failure, run_root=tmp_path)

    validation_log = json.loads((tmp_path / "supported-claim" / "validation_log.json").read_text())

    assert "check:unsupported_claim:final.output" not in {check["id"] for check in validation_log}
