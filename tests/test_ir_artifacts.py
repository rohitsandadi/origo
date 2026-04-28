from pathlib import Path

from origo.importers.local_json import load_trace_json
from origo.ir.artifact_extractor import extract_artifacts
from origo.ir.normalize import trace_to_trajectory_ir


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_trace_normalizes_to_trajectory_ir_with_ordered_steps_and_substeps():
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")

    ir = trace_to_trajectory_ir(trace)

    assert ir.trajectory_id == "rag-stale-policy"
    assert ir.instruction == trace.task
    assert [step.span_id for step in ir.steps] == [
        "user",
        "retrieval_query",
        "policy_old",
        "current_policy_tool",
        "summary",
        "final",
    ]
    assert ir.steps[2].kind == "retrieved_chunk"
    assert ir.steps[2].substeps[0].artifact_ids == ["policy_old.output"]
    assert ir.steps[-1].substeps[0].role == "assistant"
    assert ir.steps[-1].substeps[0].artifact_ids == ["final.output"]


def test_artifact_extraction_creates_stable_evidence_units_with_source_spans():
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")
    ir = trace_to_trajectory_ir(trace)

    artifacts = extract_artifacts(ir)
    by_id = {artifact.id: artifact for artifact in artifacts}

    assert by_id["policy_old.output"].kind == "retrieved_chunk"
    assert by_id["policy_old.output"].span_id == "policy_old"
    assert "90 days" in by_id["policy_old.output"].text
    assert by_id["current_policy_tool.output"].kind == "tool_result"
    assert "30 days" in by_id["current_policy_tool.output"].text
    assert by_id["final.output"].kind == "final_output"
    assert "90 days" in by_id["final.output"].text


def test_artifact_extraction_records_input_artifact_references_for_dataflow():
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")
    ir = trace_to_trajectory_ir(trace)

    artifacts = extract_artifacts(ir)
    by_id = {artifact.id: artifact for artifact in artifacts}

    assert by_id["summary.output"].metadata["input_artifact_ids"] == [
        "policy_old.output",
        "current_policy_tool.output",
    ]
    assert by_id["policy_old.output"].included_in_artifact_ids == ["summary.output"]
    assert by_id["current_policy_tool.output"].included_in_artifact_ids == ["summary.output"]
