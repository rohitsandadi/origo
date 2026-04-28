from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from origo.importers.local_json import load_failure_yaml, load_trace_json
from origo.reports.cards import analyze_traceback
from origo.reports.json_report import report_to_json
from origo.reports.markdown import render_markdown


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, json.JSONDecodeError, ValidationError, ValueError, KeyError) as exc:
        print(f"origo: error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="origo", description="Stack traces for bad AI outputs.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser("validate-trace", help="Validate a local JSON trace.")
    validate.add_argument("--trace", required=True, help="Path to trace JSON.")
    validate.set_defaults(func=_validate_trace)

    explain = subcommands.add_parser("explain", help="Explain a bad output from a trace and failure spec.")
    explain.add_argument("--trace", required=True, help="Path to trace JSON.")
    explain.add_argument("--failure", required=True, help="Path to failure YAML.")
    explain.add_argument("--format", choices=("markdown", "json"), default="markdown")
    explain.add_argument("--out", help="Output file. Prints to stdout when omitted.")
    explain.set_defaults(func=_explain)

    demo = subcommands.add_parser("demo", help="Run a canned Origo demo.")
    demo.add_argument("name", choices=("rag-stale-policy",), help="Demo name.")
    demo.set_defaults(func=_demo)

    return parser


def _validate_trace(args: argparse.Namespace) -> int:
    trace = load_trace_json(args.trace)
    missing = _missing_debuggability_fields(trace)
    level = "high" if not missing else "medium" if len(missing) <= 2 else "low"
    print(f"Trace debuggability: {level}")
    print(f"run_id: {trace.run_id}")
    print(f"spans: {len(trace.spans)}")
    if missing:
        print("Missing:")
        for item in missing:
            print(f"  - {item}")
    return 0


def _explain(args: argparse.Namespace) -> int:
    trace = load_trace_json(args.trace)
    failure = load_failure_yaml(args.failure)
    report = analyze_traceback(trace, failure)
    rendered = _render_report(report, args.format)
    if args.out:
        Path(args.out).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


def _demo(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[1]
    trace_path = root / "examples" / "rag_stale_policy" / "trace.json"
    failure_path = root / "examples" / "rag_stale_policy" / "failure.yaml"
    report = analyze_traceback(load_trace_json(trace_path), load_failure_yaml(failure_path))
    print(render_markdown(report), end="")
    return 0


def _render_report(report, format_name: str) -> str:
    if format_name == "json":
        return json.dumps(report_to_json(report), indent=2) + "\n"
    return render_markdown(report)


def _missing_debuggability_fields(trace) -> list[str]:
    missing: list[str] = []
    final_span = trace.final_output_span()
    if final_span is not None and final_span.input is None:
        missing.append("final assembled prompt")
    if any(span.kind == "retrieval" for span in trace.spans) and not any(
        "score" in span.metadata or "scores" in span.metadata for span in trace.spans if span.kind == "retrieved_chunk"
    ):
        missing.append("retrieval scores")
    if any(span.kind == "validator" for span in trace.spans) and not any(
        "criteria" in span.metadata for span in trace.spans if span.kind == "validator"
    ):
        missing.append("validator criteria")
    return missing


if __name__ == "__main__":
    raise SystemExit(main())
