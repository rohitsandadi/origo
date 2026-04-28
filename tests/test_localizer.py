from pathlib import Path

from origo.analysis.localizer import localize_from_evidence_pack
from origo.importers.local_json import load_failure_yaml, load_trace_json
from origo.pipeline import analyze_with_artifacts
from origo.schema.failure import FailureSpec
from origo.schema.trace import TraceRun, TraceSpan


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_localizer_selects_top_artifact_candidate_from_evidence_pack(tmp_path):
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")
    failure = load_failure_yaml(EXAMPLES_DIR / "rag_stale_policy" / "failure.yaml")
    result = analyze_with_artifacts(trace, failure, run_root=tmp_path)

    localization = localize_from_evidence_pack(result.evidence_pack)

    assert localization.selected_candidate_artifact_ids == ["policy_old.output"]
    assert localization.failure_category == "stale_retrieval"
    assert localization.confidence > 0
    assert localization.insufficient_data is False


def test_pipeline_writes_localization_and_reports_insufficient_trace_data(tmp_path):
    trace = TraceRun(
        run_id="thin-trace",
        spans=[TraceSpan(id="final", kind="final_output", output="The answer is unsupported.")],
        final_output_span_id="final",
    )
    failure = FailureSpec(
        failure_id="unsupported",
        bad_output="The answer is unsupported.",
        expected="The trace should contain supporting evidence.",
        failure_type="unsupported_claim",
    )

    result = analyze_with_artifacts(trace, failure, run_root=tmp_path)

    assert result.localization.insufficient_data is True
    assert "No culprit candidates" in result.localization.uncertainty
    assert (tmp_path / "thin-trace" / "localization.json").exists()
    assert "insufficient trace data" in result.report.missing_evidence[0].lower()
