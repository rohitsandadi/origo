import json
from pathlib import Path

from origo.importers.local_json import load_failure_yaml, load_trace_json
from origo.invariants.library import load_builtin_static_invariants
from origo.pipeline import analyze_with_artifacts


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_builtin_static_invariant_library_names_core_failure_modes():
    invariants = load_builtin_static_invariants()
    by_id = {invariant.id: invariant for invariant in invariants}

    assert "builtin:stale_retrieval" in by_id
    assert "retrieved_chunk" in by_id["builtin:stale_retrieval"].target_kinds
    assert "builtin:ignored_evidence" in by_id
    assert by_id["builtin:ignored_evidence"].check_type == "structured"


def test_pipeline_writes_invariant_artifacts_and_check_references(tmp_path):
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")
    failure = load_failure_yaml(EXAMPLES_DIR / "rag_stale_policy" / "failure.yaml")

    analyze_with_artifacts(trace, failure, run_root=tmp_path)

    run_dir = tmp_path / "rag-stale-policy"
    static_invariants = json.loads((run_dir / "invariants_static.json").read_text(encoding="utf-8"))
    dynamic_invariants = json.loads((run_dir / "invariants_dynamic.json").read_text(encoding="utf-8"))
    validation_log = json.loads((run_dir / "validation_log.json").read_text(encoding="utf-8"))

    assert {invariant["id"] for invariant in static_invariants} >= {
        "builtin:stale_retrieval",
        "builtin:ignored_evidence",
    }
    assert dynamic_invariants == []
    assert validation_log[0]["invariant_id"] is not None
    assert "builtin:stale_retrieval" in {check["invariant_id"] for check in validation_log}
