from pathlib import Path

from origo.extraction.actions import extract_actions
from origo.extraction.claims import extract_claims
from origo.failure.target import select_failure_target
from origo.importers.local_json import load_failure_yaml, load_trace_json
from origo.ir.artifact_extractor import extract_artifacts
from origo.ir.normalize import trace_to_trajectory_ir
from origo.pipeline import analyze_with_artifacts


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_select_failure_target_matches_bad_output_to_final_artifact():
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")
    failure = load_failure_yaml(EXAMPLES_DIR / "rag_stale_policy" / "failure.yaml")
    artifacts = extract_artifacts(trace_to_trajectory_ir(trace))

    target = select_failure_target(failure, artifacts)

    assert target.id == "failure_target:rag-stale-policy"
    assert target.final_output_artifact_id == "final.output"
    assert target.final_output_span_id == "final"
    assert target.match_status == "matched"
    assert target.bad_output == failure.bad_output


def test_extract_claims_ties_bad_output_claim_to_artifact():
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")
    failure = load_failure_yaml(EXAMPLES_DIR / "rag_stale_policy" / "failure.yaml")
    artifacts = extract_artifacts(trace_to_trajectory_ir(trace))
    target = select_failure_target(failure, artifacts)

    claims = extract_claims(target)

    assert len(claims) == 1
    assert claims[0].id == "claim:bad_output"
    assert claims[0].text == failure.bad_output
    assert claims[0].source_artifact_id == "final.output"
    assert claims[0].source_span_id == "final"
    assert claims[0].extraction_method == "manual"


def test_extract_actions_detects_structured_final_action_artifacts():
    trace = load_trace_json(EXAMPLES_DIR / "ignored_tool_output" / "trace.json")
    ir = trace_to_trajectory_ir(trace)
    artifacts = extract_artifacts(ir)
    final_artifact = next(artifact for artifact in artifacts if artifact.id == "final.output")
    final_artifact.content = {"action_type": "refund_decision", "arguments": {"order_id": "A100"}}

    actions = extract_actions([final_artifact])

    assert len(actions) == 1
    assert actions[0].id == "action:final.output"
    assert actions[0].source_artifact_id == "final.output"
    assert actions[0].action_type == "refund_decision"
    assert actions[0].arguments == {"order_id": "A100"}
    assert actions[0].extraction_method == "heuristic"


def test_pipeline_writes_failure_target_claims_and_actions(tmp_path):
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")
    failure = load_failure_yaml(EXAMPLES_DIR / "rag_stale_policy" / "failure.yaml")

    analyze_with_artifacts(trace, failure, run_root=tmp_path)

    run_dir = tmp_path / "rag-stale-policy"
    assert (run_dir / "failure_target.json").exists()
    assert (run_dir / "claims.json").exists()
    assert (run_dir / "actions.json").exists()
    assert "final.output" in (run_dir / "claims.json").read_text(encoding="utf-8")
