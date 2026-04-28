import json

from origo.importers.langfuse import load_langfuse_json


def test_langfuse_json_imports_trace_observations_and_scores(tmp_path):
    payload = {
        "trace": {
            "id": "trace-1",
            "name": "refund-agent",
            "input": "Can order A100 be refunded?",
            "output": "Order A100 cannot be refunded.",
            "metadata": {"environment": "test"},
        },
        "observations": [
            {
                "id": "obs-tool",
                "traceId": "trace-1",
                "type": "TOOL",
                "name": "check_refund_eligibility",
                "input": {"order_id": "A100"},
                "output": {"status": "eligible", "reason": "inside 30 days"},
            },
            {
                "id": "obs-final",
                "traceId": "trace-1",
                "parentObservationId": "obs-tool",
                "type": "GENERATION",
                "name": "final_answer",
                "input": [{"role": "tool", "content": "eligible"}],
                "output": "Order A100 cannot be refunded.",
            },
        ],
        "scores": [
            {
                "id": "score-1",
                "name": "tool_response_handling",
                "value": 0,
                "observationId": "obs-final",
                "comment": "Ignored the tool result.",
            }
        ],
    }
    path = tmp_path / "langfuse.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    trace = load_langfuse_json(path)

    assert trace.run_id == "trace-1"
    assert trace.task == "Can order A100 be refunded?"
    assert trace.final_output_span_id == "obs-final"
    assert trace.get_span("trace.input").kind == "user_input"
    assert trace.get_span("obs-tool").kind == "tool_result"
    assert trace.get_span("obs-tool").output["status"] == "eligible"
    assert trace.get_span("obs-final").kind == "final_output"
    assert trace.get_span("obs-final").parent_id == "obs-tool"
    assert trace.get_span("obs-final").metadata["langfuse_scores"][0]["name"] == "tool_response_handling"
    assert trace.metadata["source_schema"] == "langfuse.json_export"
