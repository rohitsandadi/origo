import json
from pathlib import Path

from origo.importers.local_json import load_failure_yaml, load_trace_json
from origo.pipeline import analyze_with_artifacts


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_analysis_writes_validation_log_and_cites_failed_checks(tmp_path):
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")
    failure = load_failure_yaml(EXAMPLES_DIR / "rag_stale_policy" / "failure.yaml")

    analyze_with_artifacts(trace, failure, run_root=tmp_path)

    run_dir = tmp_path / "rag-stale-policy"
    validation_log = json.loads((run_dir / "validation_log.json").read_text(encoding="utf-8"))
    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_markdown = (run_dir / "report.md").read_text(encoding="utf-8")

    check_ids = {check["id"] for check in validation_log}
    assert "check:stale_retrieval:policy_old" in check_ids
    assert "check:ignored_evidence:current_policy_tool" in check_ids

    stale_check = next(check for check in validation_log if check["id"] == "check:stale_retrieval:policy_old")
    assert stale_check["status"] == "fail"
    assert stale_check["failure_mode"] == "stale_retrieval"
    assert stale_check["target_artifact_id"] == "policy_old.output"

    failed_check_ids = report_json["cards"][0]["failed_check_ids"]
    assert "check:stale_retrieval:policy_old" in failed_check_ids
    assert "check:ignored_evidence:current_policy_tool" in failed_check_ids
    assert "Failed checks:" in report_markdown
    assert "`check:stale_retrieval:policy_old`" in report_markdown
