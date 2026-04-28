import json
from pathlib import Path

from origo.importers.local_json import load_failure_yaml, load_trace_json
from origo.pipeline import analyze_with_artifacts


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_artifact_provenance_graph_connects_parent_output_to_final_output(tmp_path):
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")
    failure = load_failure_yaml(EXAMPLES_DIR / "rag_stale_policy" / "failure.yaml")

    analyze_with_artifacts(trace, failure, run_root=tmp_path)

    graph = json.loads((tmp_path / "rag-stale-policy" / "provenance_graph.json").read_text(encoding="utf-8"))
    edges = {(edge["source"], edge["target"], edge["kind"]) for edge in graph["edges"]}
    assert ("artifact:summary.output", "artifact:final.output", "generated_from") in edges


def test_pipeline_writes_artifact_candidates_and_evidence_pack(tmp_path):
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")
    failure = load_failure_yaml(EXAMPLES_DIR / "rag_stale_policy" / "failure.yaml")

    analyze_with_artifacts(trace, failure, run_root=tmp_path)

    run_dir = tmp_path / "rag-stale-policy"
    candidates = json.loads((run_dir / "culprit_candidates.json").read_text(encoding="utf-8"))
    evidence_pack = json.loads((run_dir / "evidence_pack.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))

    assert candidates[0]["artifact_id"] == "policy_old.output"
    assert candidates[0]["span_id"] == "policy_old"
    assert candidates[0]["failed_check_ids"] == ["check:stale_retrieval:policy_old"]
    assert "artifact:final.output" in candidates[0]["path"]

    assert evidence_pack["failure_target"]["final_output_artifact_id"] == "final.output"
    assert evidence_pack["claims"][0]["source_artifact_id"] == "final.output"
    assert evidence_pack["candidates"][0]["artifact_id"] == "policy_old.output"

    assert report["cards"][0]["culprit_artifact_ids"] == ["policy_old.output"]
    assert "current_policy_tool.output" in report["cards"][0]["ignored_evidence_artifact_ids"]
    assert "artifact:final.output" in report["cards"][0]["traceback_path"]
