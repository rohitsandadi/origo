# Origo

Stack traces for bad AI outputs.

Origo is a local-first traceback engine for LLM and agent failures. Give it a trace plus a wrong answer or action, and it returns culprit cards showing where the bad information came from, how it propagated, what correct evidence was ignored, and what to fix.

## Status

Origo is pre-alpha foundation work. The current code supports local fixture traces and deterministic reports, and now writes auditable intermediate artifacts for the first real analysis stages. It is not yet a complete production traceback engine: OpenInference/Phoenix/Langfuse imports, invariant generation, validation logs, and LLM-assisted localization are still being implemented.

The technical roadmap is in [docs/technical-design-v1.md](docs/technical-design-v1.md).

## Quickstart

```bash
origo validate-trace --trace examples/rag_stale_policy/trace.json
origo explain \
  --trace examples/rag_stale_policy/trace.json \
  --failure examples/rag_stale_policy/failure.yaml \
  --out report.md \
  --run-dir runs
origo demo rag-stale-policy
```

The foundation MVP is deterministic-first: local JSON traces, YAML failure specs, trajectory IR normalization, artifact extraction, exact/value evidence matching, omission detection, transparent ranking, auditable run artifacts, and Markdown/JSON reports.
