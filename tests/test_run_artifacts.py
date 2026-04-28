from pathlib import Path

from origo.importers.local_json import load_failure_yaml, load_trace_json
from origo.pipeline import analyze_with_artifacts


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_analysis_writes_auditable_stage_artifacts(tmp_path):
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")
    failure = load_failure_yaml(EXAMPLES_DIR / "rag_stale_policy" / "failure.yaml")

    result = analyze_with_artifacts(trace, failure, run_root=tmp_path)

    run_dir = tmp_path / "rag-stale-policy"
    assert result.run_dir == run_dir
    assert (run_dir / "normalized_trace.json").exists()
    assert (run_dir / "trajectory_ir.json").exists()
    assert (run_dir / "artifacts.json").exists()
    assert (run_dir / "provenance_graph.json").exists()
    assert (run_dir / "report.json").exists()
    assert (run_dir / "report.md").exists()
    assert "policy_old.output" in (run_dir / "artifacts.json").read_text(encoding="utf-8")


def test_analysis_writes_artifact_level_provenance_graph(tmp_path):
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")
    failure = load_failure_yaml(EXAMPLES_DIR / "rag_stale_policy" / "failure.yaml")

    analyze_with_artifacts(trace, failure, run_root=tmp_path)

    graph = (tmp_path / "rag-stale-policy" / "provenance_graph.json").read_text(encoding="utf-8")
    assert '"id": "artifact:policy_old.output"' in graph
    assert '"id": "artifact:summary.output"' in graph
    assert '"source": "artifact:policy_old.output"' in graph
    assert '"target": "artifact:summary.output"' in graph
    assert '"kind": "generated_from"' in graph
