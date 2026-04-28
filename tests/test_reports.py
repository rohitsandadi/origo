from pathlib import Path

from origo.importers.local_json import load_failure_yaml, load_trace_json
from origo.reports.cards import analyze_traceback
from origo.reports.json_report import report_to_json
from origo.reports.markdown import render_markdown


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_markdown_report_contains_culprit_path_ignored_evidence_and_fix():
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")
    failure = load_failure_yaml(EXAMPLES_DIR / "rag_stale_policy" / "failure.yaml")

    report = analyze_traceback(trace, failure)
    markdown = render_markdown(report)

    assert report.cards[0].culprit_span_id == "policy_old"
    assert "Stale policy chunk influenced the final answer" in markdown
    assert "`policy_old`" in markdown
    assert "`summary`" in markdown
    assert "`final`" in markdown
    assert "current_policy_tool" in markdown
    assert "Prefer current policy tool output over stale retrieved docs." in markdown


def test_json_report_is_machine_readable_and_includes_span_snippets():
    trace = load_trace_json(EXAMPLES_DIR / "rag_stale_policy" / "trace.json")
    failure = load_failure_yaml(EXAMPLES_DIR / "rag_stale_policy" / "failure.yaml")

    report = analyze_traceback(trace, failure)
    payload = report_to_json(report)

    assert payload["failure_id"] == "rag-stale-policy"
    assert payload["cards"][0]["culprit_span_id"] == "policy_old"
    assert "90 days" in payload["cards"][0]["culprit_snippet"]
    assert payload["cards"][0]["ignored_evidence"][0]["span_id"] == "current_policy_tool"
    assert "30 days" in payload["cards"][0]["ignored_evidence"][0]["snippet"]


def test_ignored_tool_output_report_keeps_tool_result_as_ignored_evidence_not_culprit():
    trace = load_trace_json(EXAMPLES_DIR / "ignored_tool_output" / "trace.json")
    failure = load_failure_yaml(EXAMPLES_DIR / "ignored_tool_output" / "failure.yaml")

    report = analyze_traceback(trace, failure)

    assert "tool_result" not in [card.culprit_span_id for card in report.cards]
    assert report.cards[0].ignored_evidence[0].span_id == "tool_result"
    assert "eligible" in report.cards[0].ignored_evidence[0].snippet
