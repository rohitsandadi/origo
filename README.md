# Origo

Stack traces for bad AI outputs.

Origo is a local-first diagnosis engine for LLM and agent failures. Give it a
trace and a bad answer, and Origo turns the run into culprit cards: the stale
retrieval chunk, ignored tool result, unsupported claim, wrong tool argument, or
broken summary that likely caused the output.

Origo is built for the moment after an eval fails and the usual answer is still
"go read the whole trace." It reads the trace for you, preserves the evidence,
and writes an auditable report.

## What Origo Does

Observability tools show what ran. Eval tools show whether it passed. Origo
connects the two:

```text
bad output
  <- final prompt / response
  <- summary, memory, tool result, or retrieved chunk
  <- source evidence that was stale, omitted, ignored, or unsupported
```

The output is a culprit-card report with:

- the failed output and expected output;
- ranked culprit artifacts and spans;
- exact evidence snippets;
- ignored or omitted evidence;
- failed check IDs;
- traceback paths through the run;
- suggested fixes.

## Status

Origo is pre-alpha. The current version is a CLI and Python package for local
analysis, not a hosted observability service or trace capture SDK.

What works today:

- local JSON traces and failure YAML;
- OpenInference, Phoenix, Langfuse, and TraceRoot JSON importers;
- trajectory IR normalization;
- artifact extraction for prompts, final outputs, retrieved chunks, summaries,
  tool calls, tool results, memory, state, and validator results;
- deterministic checks for stale retrieval, ignored evidence, imported failing
  scores, unsupported claims, and wrong tool arguments;
- culprit candidates, evidence packs, deterministic localization, and Markdown
  or JSON reports;
- durable run artifacts so every report can be audited from disk.

## Installation

From the repository root:

```bash
python -m pip install -e ".[dev]"
```

Or run the package directly during development:

```bash
PYTHONPATH=. python -m origo.cli --help
```

## Quick Start

Validate a trace:

```bash
origo validate-trace \
  --trace examples/rag_stale_policy/trace.json
```

Explain a bad output and write auditable artifacts:

```bash
origo explain \
  --trace examples/rag_stale_policy/trace.json \
  --failure examples/rag_stale_policy/failure.yaml \
  --out report.md \
  --run-dir runs
```

Run the bundled demo:

```bash
origo demo rag-stale-policy
```

Write JSON instead of Markdown:

```bash
origo explain \
  --trace examples/rag_stale_policy/trace.json \
  --failure examples/rag_stale_policy/failure.yaml \
  --format json \
  --out report.json \
  --run-dir runs
```

## Trace Formats

Use `--trace-format` to import traces from common observability exports:

```bash
origo explain \
  --trace path/to/trace.json \
  --trace-format openinference \
  --failure path/to/failure.yaml \
  --run-dir runs
```

Supported values:

| Format | Use it for |
| --- | --- |
| `local` | Origo fixtures and simple local traces |
| `openinference` | OpenInference-style span JSON |
| `phoenix` | Phoenix span exports |
| `langfuse` | Langfuse traces, observations, and scores |
| `traceroot` | TraceRoot / OTEL-style trace exports with git metadata |

## Failure Specs

A failure spec tells Origo what went wrong, not where the culprit is:

```yaml
failure_id: refund-window-stale
bad_output: Refunds are available within 90 days of purchase.
expected: Refunds are available within 30 days of purchase.
failure_type: stale_retrieval
```

Origo then finds the final output artifact, extracts the failed claim or action,
matches supporting and contradicting evidence, and ranks likely causes.

## How It Works

Each `origo explain --run-dir runs` execution writes a directory like:

```text
runs/<run_id>/
  normalized_trace.json
  failure_spec.json
  failure_target.json
  trajectory_ir.json
  artifacts.json
  claims.json
  actions.json
  provenance_graph.json
  invariants_static.json
  invariants_dynamic.json
  validation_log.json
  culprit_candidates.json
  evidence_pack.json
  localization.json
  report.json
  report.md
```

The pipeline is deterministic-first:

1. Import and normalize the trace.
2. Extract artifact-level evidence.
3. Select the failed output target.
4. Extract claims and structured actions.
5. Build provenance edges between artifacts.
6. Run built-in checks.
7. Rank culprit candidates.
8. Localize the root cause from an evidence pack.
9. Write Markdown and JSON reports.

## Python API

```python
from pathlib import Path

from origo.importers.local_json import load_failure_yaml, load_trace_json
from origo.pipeline import analyze_with_artifacts

trace = load_trace_json("examples/rag_stale_policy/trace.json")
failure = load_failure_yaml("examples/rag_stale_policy/failure.yaml")

result = analyze_with_artifacts(trace, failure, run_root=Path("runs"))

print(result.report.cards[0].title)
print(result.localization.explanation)
```

## Development

Run the test suite:

```bash
pytest
```

The codebase is organized around small, auditable stages:

```text
origo/
  importers/     trace import adapters
  ir/            trajectory IR and artifact extraction
  failure/       failed-output target selection
  extraction/    claim and action extraction
  provenance/    artifact-level graph construction
  invariants/    built-in checks and validation logs
  analysis/      candidates, evidence packs, localization
  reports/       Markdown and JSON culprit cards
  runs/          local artifact writer
```

Origo should stay local-first, evidence-citing, and honest about uncertainty. If
the trace is missing the final prompt, tool result, retrieved evidence, or source
context needed to diagnose a failure, the report should say so.
