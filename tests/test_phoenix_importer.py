import json

from origo.importers.phoenix import load_phoenix_json


def test_phoenix_span_json_imports_trace_and_retrieval_documents(tmp_path):
    payload = {
        "spans": [
            {
                "name": "retrieve_policy",
                "context": {"trace_id": "trace-1", "span_id": "span-retrieval"},
                "span_kind": "RETRIEVER",
                "parent_id": None,
                "attributes": {
                    "input": {"value": "refund policy"},
                    "retrieval": {
                        "documents": [
                            {
                                "document": {
                                    "id": "policy-2023",
                                    "content": "Archived refund policy: 90 days.",
                                    "score": 0.7,
                                }
                            }
                        ]
                    },
                },
            },
            {
                "name": "final_answer",
                "context": {"trace_id": "trace-1", "span_id": "span-final"},
                "span_kind": "LLM",
                "parent_id": "span-retrieval",
                "attributes": {
                    "output": {"value": "Refunds are available for 90 days."},
                    "origo": {"final_output": True},
                },
            },
        ]
    }
    path = tmp_path / "phoenix.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    trace = load_phoenix_json(path)

    assert trace.run_id == "trace-1"
    assert trace.final_output_span_id == "span-final"
    assert trace.get_span("span-retrieval").kind == "retrieval"
    assert trace.get_span("span-retrieval").output == ["span-retrieval.document.0"]
    assert trace.get_span("span-retrieval.document.0").kind == "retrieved_chunk"
    assert "90 days" in trace.get_span("span-retrieval.document.0").output
    assert trace.get_span("span-final").kind == "final_output"
    assert trace.metadata["source_schema"] == "phoenix.span_json"
