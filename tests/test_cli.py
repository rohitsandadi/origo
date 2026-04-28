import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "origo.cli", *args],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def test_validate_trace_cli_reports_debuggability():
    result = run_cli("validate-trace", "--trace", "examples/rag_stale_policy/trace.json")

    assert result.returncode == 0
    assert "Trace debuggability:" in result.stdout
    assert "run_id: rag-stale-policy" in result.stdout


def test_explain_cli_writes_markdown_report(tmp_path):
    out = tmp_path / "report.md"

    result = run_cli(
        "explain",
        "--trace",
        "examples/rag_stale_policy/trace.json",
        "--failure",
        "examples/rag_stale_policy/failure.yaml",
        "--out",
        str(out),
    )

    assert result.returncode == 0
    assert out.exists()
    assert "Stale policy chunk influenced the final answer" in out.read_text(encoding="utf-8")


def test_explain_cli_writes_json_report(tmp_path):
    out = tmp_path / "report.json"

    result = run_cli(
        "explain",
        "--trace",
        "examples/rag_stale_policy/trace.json",
        "--failure",
        "examples/rag_stale_policy/failure.yaml",
        "--format",
        "json",
        "--out",
        str(out),
    )

    assert result.returncode == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["cards"][0]["culprit_span_id"] == "policy_old"


def test_explain_cli_rejects_unsupported_text_format():
    result = run_cli(
        "explain",
        "--trace",
        "examples/rag_stale_policy/trace.json",
        "--failure",
        "examples/rag_stale_policy/failure.yaml",
        "--format",
        "text",
    )

    assert result.returncode != 0


def test_demo_cli_prints_stale_policy_report():
    result = run_cli("demo", "rag-stale-policy")

    assert result.returncode == 0
    assert "Origo Traceback Report" in result.stdout
    assert "policy_old" in result.stdout
