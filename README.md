# Origo

Stack traces for bad AI outputs.

Origo is a local-first traceback engine for LLM and agent failures. Give it a trace plus a wrong answer or action, and it returns culprit cards showing where the bad information came from, how it propagated, what correct evidence was ignored, and what to fix.

## Quickstart

```bash
origo validate-trace --trace examples/rag_stale_policy/trace.json
origo explain \
  --trace examples/rag_stale_policy/trace.json \
  --failure examples/rag_stale_policy/failure.yaml \
  --out report.md
origo demo rag-stale-policy
```

The foundation MVP is deterministic-first: local JSON traces, YAML failure specs, exact/value evidence matching, omission detection, transparent ranking, and Markdown/JSON reports.
