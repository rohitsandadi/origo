import json
from pathlib import Path

from origo.importers.openinference import load_openinference_json


def test_openinference_otlp_json_imports_spans_and_retrieval_documents(tmp_path):
    payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            _span(
                                name="retrieve_policy",
                                trace_id="00000000000000000000000000000001",
                                span_id="0000000000000001",
                                attributes=[
                                    _attr("openinference.span.kind", "RETRIEVER"),
                                    _attr("input.value", "refund policy"),
                                    _attr(
                                        "retrieval.documents",
                                        [
                                            {
                                                "document.id": "policy-2023",
                                                "document.content": "Archived policy: refunds are available for 90 days.",
                                                "document.score": 0.82,
                                            }
                                        ],
                                    ),
                                ],
                            ),
                            _span(
                                name="get_current_policy",
                                trace_id="00000000000000000000000000000001",
                                span_id="0000000000000002",
                                attributes=[
                                    _attr("openinference.span.kind", "TOOL"),
                                    _attr("input.value", {"policy": "refunds"}),
                                    _attr("output.value", "Current policy: refunds are available for 30 days."),
                                ],
                            ),
                            _span(
                                name="final_answer",
                                trace_id="00000000000000000000000000000001",
                                span_id="0000000000000003",
                                parent_span_id="0000000000000001",
                                attributes=[
                                    _attr("openinference.span.kind", "LLM"),
                                    _attr("origo.final_output", True),
                                    _attr("output.value", "Refunds are available for 90 days."),
                                ],
                            ),
                        ]
                    }
                ]
            }
        ]
    }
    path = tmp_path / "otel.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    trace = load_openinference_json(path)

    assert trace.run_id == "00000000000000000000000000000001"
    assert trace.final_output_span_id == "0000000000000003"
    assert trace.get_span("0000000000000001").kind == "retrieval"
    assert trace.get_span("0000000000000001").output == ["0000000000000001.document.0"]
    chunk = trace.get_span("0000000000000001.document.0")
    assert chunk.kind == "retrieved_chunk"
    assert chunk.parent_id == "0000000000000001"
    assert "90 days" in chunk.output
    assert chunk.metadata["document.id"] == "policy-2023"
    assert trace.get_span("0000000000000002").kind == "tool_result"
    assert trace.get_span("0000000000000003").kind == "final_output"


def _span(
    *,
    name: str,
    trace_id: str,
    span_id: str,
    attributes: list[dict],
    parent_span_id: str | None = None,
) -> dict:
    span = {
        "name": name,
        "traceId": trace_id,
        "spanId": span_id,
        "startTimeUnixNano": "1000000000",
        "endTimeUnixNano": "2000000000",
        "attributes": attributes,
    }
    if parent_span_id:
        span["parentSpanId"] = parent_span_id
    return span


def _attr(key: str, value: object) -> dict:
    return {"key": key, "value": _value(value)}


def _value(value: object) -> dict:
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_value(item) for item in value]}}
    if isinstance(value, dict):
        return {
            "kvlistValue": {
                "values": [{"key": key, "value": _value(child)} for key, child in value.items()]
            }
        }
    raise TypeError(value)
