import json

from origo.importers.traceroot import load_traceroot_json


def test_traceroot_json_imports_spans_and_git_source_context(tmp_path):
    payload = {
        "traces": [
            {
                "trace_id": "trace-1",
                "name": "refund-agent",
                "input": "Can order A100 be refunded?",
                "output": "Order A100 cannot be refunded.",
                "git_repo": "https://github.com/example/shop",
                "git_ref": "abc123",
            }
        ],
        "spans": [
            {
                "span_id": "tool-span",
                "trace_id": "trace-1",
                "parent_span_id": None,
                "name": "check_refund_eligibility",
                "span_kind": "TOOL",
                "input": {"order_id": "A100"},
                "output": {"status": "eligible"},
                "git_source_file": "app/refunds.py",
                "git_source_line": 42,
                "git_source_function": "check_refund_eligibility",
            },
            {
                "span_id": "llm-final",
                "trace_id": "trace-1",
                "parent_span_id": "tool-span",
                "name": "final_answer",
                "span_kind": "LLM",
                "output": "Order A100 cannot be refunded.",
            },
        ],
    }
    path = tmp_path / "traceroot.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    trace = load_traceroot_json(path)

    assert trace.run_id == "trace-1"
    assert trace.task == "Can order A100 be refunded?"
    assert trace.final_output_span_id == "llm-final"
    assert trace.metadata["git_repo"] == "https://github.com/example/shop"
    assert trace.metadata["git_ref"] == "abc123"
    assert trace.get_span("tool-span").kind == "tool_result"
    assert trace.get_span("tool-span").metadata["git_source_file"] == "app/refunds.py"
    assert trace.get_span("tool-span").metadata["git_source_line"] == 42
    assert trace.get_span("llm-final").kind == "final_output"
    assert trace.metadata["source_schema"] == "traceroot.clickhouse_json"
