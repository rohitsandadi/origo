# Origo Technical Design v1

Date: April 28, 2026

Status: planning document for the next implementation pass.

Audience: Origo contributors and autonomous Codex agents.

## 1. Correction From The Current MVP

The current Origo repository is a useful scaffold, but it is not yet the product
described in the design doc. It validates local JSON, builds a small deterministic
graph, and emits reports for hand-built examples. That is not enough to claim real
traceback behavior.

The product should be:

> Origo is a local-first diagnosis engine for bad LLM/agent outputs. It imports
> real traces, normalizes them into a trajectory IR, extracts the failed
> claim/action, builds an artifact-level provenance graph, runs deterministic and
> LLM-assisted checks, and emits culprit cards tied to exact evidence paths.

The current implementation should be treated as an experimental contract test,
not as the core architecture.

## 2. What The Reference Codebases Show

### AgentRx

AgentRx is the strongest implementation reference for the analysis pipeline. Its
top-level pipeline is:

```text
ir -> static -> dynamic -> check -> judge -> report
```

Important code observations:

- `run.py` persists stage artifacts under `runs/<run_name>/`, rather than hiding
  intermediate state.
- `src/ir/trajectory_ir.py` normalizes many raw trajectory shapes into one IR
  with `trajectory_id`, `instruction`, `steps`, and `substeps`.
- `src/invariants/static_invariant_generator.py` generates domain/policy/tool
  invariants before looking at a specific failed run.
- `src/invariants/dynamic_invariant_generator.py` generates per-step invariants
  conditioned on the task and trajectory prefix.
- `src/invariants/checker.py` produces explicit violation records and telemetry.
- `src/judge/judge.py` uses the violation context plus trajectory evidence to
  localize and classify root cause steps.

Lesson for Origo: real diagnosis needs normalized IR, generated or authored
checks, a validation log, and a localization step. A graph alone is not enough.

### Phoenix

Phoenix is the strongest reference for trace ingestion and evaluation
interoperability.

Important code observations:

- `phoenix.trace.schemas.Span` models OpenTelemetry/OpenInference-like spans:
  trace ID, span ID, parent ID, kind, attributes, events, status, timestamps.
- `phoenix.trace.otel.decode_otlp_span` decodes OTLP protobuf spans into Phoenix
  spans and preserves OpenInference semantic attributes such as input, output,
  retrieval documents, token counts, and span kind.
- `phoenix.db.insertion.span.insert_span` persists spans, traces, sessions,
  cumulative token counts, and cumulative error counts.
- `phoenix.trace.trace_dataset.TraceDataset` flattens spans into dataframes and
  can reconstruct spans.
- `packages/phoenix-evals` provides LLM-as-judge metrics for faithfulness,
  hallucination, tool invocation, tool selection, and tool response handling.

Lesson for Origo: do not invent trace capture. Import OpenTelemetry/OpenInference
spans and use Phoenix-style evaluator boundaries. Origo's unique layer is not
storage or UI, but output-centered attribution over these traces.

### Langfuse

Langfuse is the strongest reference for production observability data modeling.

Important code observations:

- The durable model separates traces, observations, scores, sessions, datasets,
  prompts, and eval jobs.
- `worker/src/services/IngestionService/index.ts` merges trace, observation,
  score, and dataset-run events into durable ClickHouse records.
- Observation records preserve input, output, type, parent observation ID,
  model, prompt, usage, cost, tool definitions, and tool calls.
- Scores attach to traces, observations, sessions, or dataset runs.
- Observation evals download observation data, extract configured variables, run
  LLM-as-judge evaluation, and persist scores.

Lesson for Origo: interop should map Langfuse traces/observations/scores into
Origo IR. Origo should not recreate Langfuse. It should consume this data and
produce richer causal cards than score dashboards can produce.

### TraceRoot

TraceRoot is the closest product-spirit reference for AI-assisted RCA.

Important code observations:

- `backend/worker/otel_transform.py` transforms OTLP JSON into ClickHouse trace
  and span records.
- The transform extracts span kind, input/output, model, token counts, cost,
  status, metadata, user/session IDs, and git source fields.
- It preserves path metadata such as `traceroot.span.path` and
  `traceroot.span.ids_path`, which is necessary when traces arrive out of order.
- `backend/worker/ingest_tasks.py` stores raw OTEL batches in S3, processes them
  asynchronously, inserts to ClickHouse, and publishes live span updates.
- The docs describe an AI agent that reads failing traces, clones the production
  repository at the relevant commit, inspects source lines from span attributes,
  and correlates trace data with code.

Lesson for Origo: source context and git metadata matter eventually. For v1,
Origo should preserve source references in the IR and reports, even if it does
not yet clone repositories or open fix PRs.

## 3. Product Boundary

Origo should not be:

- a trace capture SDK;
- a hosted observability backend;
- a Phoenix/Langfuse dashboard clone;
- a generic LLM eval runner;
- an agent framework.

Origo should be:

- a portable local analyzer over existing traces;
- a canonical trajectory IR plus artifact graph;
- a failure-specific checking and localization engine;
- a report generator that explains bad outputs with exact evidence.

The wedge is bad-output provenance:

```text
bad claim/action
  <- final response
  <- prompt/context artifact
  <- summary/planner/tool/retriever artifact
  <- source evidence or omitted source evidence
```

## 4. Target Architecture

```text
raw trace/export
  -> import adapter
  -> trajectory IR
  -> artifact extraction
  -> failure target selection
  -> claim/action extraction
  -> provenance graph
  -> invariant/check execution
  -> evidence pack
  -> culprit candidate generation
  -> localizer/judge
  -> culprit-card report
```

Each run writes durable local artifacts:

```text
runs/<run_id>/
  raw_trace.json
  normalized_trace.json
  trajectory_ir.json
  failure_spec.json
  artifacts.json
  claims.json
  actions.json
  provenance_graph.json
  invariants_static.json
  invariants_dynamic.json
  validation_log.json
  culprit_candidates.json
  report.json
  report.md
```

Artifacts are essential. If a report cannot be audited from these files, Origo is
not doing real traceback.

## 5. Core Data Model

### Trajectory IR

The IR should be closer to AgentRx than to the current `TraceRun` schema.

```python
class TrajectoryIR(BaseModel):
    trajectory_id: str
    instruction: str | None
    steps: list[TrajectoryStep]
    metadata: dict[str, Any]

class TrajectoryStep(BaseModel):
    index: int
    span_id: str | None
    name: str | None
    kind: StepKind
    substeps: list[TrajectorySubstep]
    parent_span_id: str | None
    start_time: str | None
    end_time: str | None
    attributes: dict[str, Any]

class TrajectorySubstep(BaseModel):
    sub_index: int
    role: Literal["user", "system", "assistant", "tool", "retriever", "memory", "validator", "agent"]
    content: Any
    artifact_ids: list[str]
    source_span_id: str | None
    metadata: dict[str, Any]
```

### Artifacts

Artifacts are the units of evidence. Spans are too coarse.

```python
class Artifact(BaseModel):
    id: str
    kind: Literal[
        "message",
        "prompt",
        "retrieved_document",
        "retrieved_chunk",
        "tool_call",
        "tool_result",
        "memory_item",
        "summary",
        "state",
        "validator_result",
        "final_output",
        "source_code_ref",
    ]
    span_id: str | None
    content: Any
    text: str | None
    created_at_step: int | None
    included_in_artifact_ids: list[str]
    metadata: dict[str, Any]
```

### Failure Target

The failure spec should identify the bad output, but Origo should not require
the user to provide culprit span IDs.

```python
class FailureSpec(BaseModel):
    failure_id: str
    bad_output: str
    expected_output: str | None
    final_output_span_id: str | None
    final_output_artifact_id: str | None
    failure_type_hint: str | None
    user_notes: str | None
```

### Claims And Actions

```python
class OutputClaim(BaseModel):
    id: str
    text: str
    source_artifact_id: str
    source_span_id: str | None
    subject: str | None
    predicate: str | None
    object: str | None
    qualifiers: dict[str, Any]
    extraction_method: Literal["manual", "heuristic", "llm"]

class OutputAction(BaseModel):
    id: str
    source_artifact_id: str
    source_span_id: str | None
    tool_name: str | None
    action_type: str
    arguments: dict[str, Any]
    extraction_method: Literal["manual", "heuristic", "llm"]
```

### Provenance Graph

```python
class ProvenanceNode(BaseModel):
    id: str
    kind: Literal["step", "span", "artifact", "claim", "action", "failure", "check"]
    ref_id: str
    label: str
    content_preview: str | None
    metadata: dict[str, Any]

class ProvenanceEdge(BaseModel):
    source: str
    target: str
    kind: Literal[
        "parent_child_span",
        "temporal_next",
        "contains_artifact",
        "included_in_prompt",
        "retrieved_for",
        "tool_call_to_result",
        "written_to_state",
        "read_from_state",
        "summarized_into",
        "generated_from",
        "supports_claim",
        "contradicts_claim",
        "omitted_from_prompt",
        "ignored_by_output",
        "validated_by",
        "failed_check",
    ]
    confidence: float
    method: Literal["trace_structure", "exact", "structured", "embedding", "llm", "heuristic"]
    evidence_refs: list[str]
    metadata: dict[str, Any]
```

### Validation Log

The validation log is what the current MVP lacks.

```python
class CheckResult(BaseModel):
    id: str
    invariant_id: str | None
    check_name: str
    target_step_id: str | None
    target_artifact_id: str | None
    status: Literal["pass", "fail", "skip", "error", "unknown"]
    failure_mode: str | None
    explanation: str
    evidence_refs: list[str]
    confidence: float
    checker_kind: Literal["deterministic", "python", "llm_judge", "replay"]
```

### Culprit Card

```python
class CulpritCard(BaseModel):
    id: str
    title: str
    failed_output: str
    expected_output: str | None
    failure_modes: list[str]
    culprit_artifact_ids: list[str]
    culprit_span_ids: list[str]
    traceback_path: list[str]
    ignored_evidence_artifact_ids: list[str]
    failed_checks: list[str]
    confidence: float
    uncertainty: str | None
    suggested_fixes: list[str]
```

## 6. Import Adapters

### Local JSON

Keep local JSON support for fixtures, tests, and demos, but make it import into
`TrajectoryIR` plus `Artifact` records. It should no longer be the architecture.

### OpenInference / OTLP

This should be the first serious importer.

Map:

- OTLP trace ID -> `TrajectoryIR.trajectory_id`
- OTLP span ID -> `TrajectoryStep.span_id`
- parent span ID -> parent and graph edge
- `openinference.span.kind` -> step kind
- `input.value` / `output.value` -> message/prompt/final artifacts
- retrieval document attributes -> retrieved document/chunk artifacts
- tool attributes and events -> tool call/result artifacts
- exception events -> check/error artifacts
- token/cost attributes -> metadata only

### Phoenix

Phoenix exports are already close to OpenInference spans. Origo should support:

- Phoenix span JSON;
- Phoenix trace dataset dataframe/parquet later;
- Phoenix evaluation annotations as imported `CheckResult` or score artifacts.

### Langfuse

Map Langfuse:

- trace -> trajectory;
- observation -> step/span;
- parent observation ID -> structural edge;
- observation input/output -> artifacts;
- tool definitions/calls -> tool artifacts;
- score -> imported check result;
- dataset item expected output -> possible failure spec seed.

### TraceRoot

Map TraceRoot:

- OTLP-style trace/span records -> trajectory and artifacts;
- `traceroot.git.*` attributes -> source code reference artifacts;
- path and IDs-path metadata -> parent reconstruction hints;
- status/error fields -> check/error artifacts.

## 7. Analysis Pipeline

### Stage 1: Normalize

Input is raw trace/export. Output is `trajectory_ir.json`.

Acceptance:

- handles out-of-order spans;
- preserves span IDs and parent IDs;
- extracts input/output from common OpenInference, Langfuse, Phoenix, and
  TraceRoot fields;
- marks missing root/final-output ambiguity instead of guessing silently.

### Stage 2: Extract Artifacts

Input is trajectory IR. Output is `artifacts.json`.

Acceptance:

- final output is an artifact;
- every prompt/message/tool result/retrieved chunk gets an artifact ID;
- artifacts keep exact snippets and source span IDs;
- structured values remain structured and also get normalized text.

### Stage 3: Select Failed Output Target

Input is failure spec plus final output artifacts. Output is failure target.

Acceptance:

- if user supplies exact bad output text, match it to final output;
- if multiple matches exist, require disambiguation or mark ambiguity;
- do not require user-supplied culprit IDs.

### Stage 4: Extract Claims And Actions

For v1, support:

- manual bad-output text from failure spec;
- heuristic claim extraction for final answer sentences;
- heuristic action extraction for tool calls and final structured actions;
- optional LLM extractor behind a flag.

Acceptance:

- one bad claim/action is tied to final output artifact;
- extraction result includes method and confidence.

### Stage 5: Build Provenance Graph

Build graph edges in layers:

1. Structural: parent-child spans, temporal order, contains artifact.
2. Inclusion: prompt contains message/chunk/tool result.
3. Data flow: retrieved chunk, tool result, summary, state write/read.
4. Semantic: supports/contradicts claim.
5. Omission: evidence existed but was not included or was ignored.
6. Check: validation log results attach to target artifacts/steps.

Acceptance:

- parent-child edges never count as evidence by themselves;
- every semantic edge cites snippets and method;
- omitted evidence is represented as an edge, not just report prose.

### Stage 6: Generate Or Load Invariants

Use an invariant schema inspired by AgentRx:

```python
class Invariant(BaseModel):
    id: str
    name: str
    scope: Literal["static", "dynamic"]
    target_kinds: list[str]
    trigger: str
    check_type: Literal["python", "structured", "llm_judge"]
    assertion: str
    code: str | None
    prompt: str | None
    metadata: dict[str, Any]
```

Initial invariant sources:

- built-in deterministic library for RAG/tool handling;
- user-provided policy YAML;
- optional LLM-generated static invariants from policy docs/tool schemas;
- optional LLM-generated dynamic invariants from trajectory prefixes.

Acceptance:

- invariant generation is optional;
- hand-authored invariant library works without LLM calls;
- all generated invariants are persisted and reviewable.

### Stage 7: Run Checks

Run deterministic checks first:

- tool result present but absent from final prompt;
- retrieved stale chunk contradicts newer tool result;
- final claim unsupported by included evidence;
- final claim contradicted by included evidence;
- tool arguments conflict with user request;
- validator ran but did not check relevant failure type.

Run LLM judge checks only when deterministic evidence is insufficient.

Acceptance:

- `validation_log.json` exists for every explanation;
- skipped checks explain why they skipped;
- failed checks cite artifacts and snippets.

### Stage 8: Generate Culprit Candidates

Candidates are not just spans. Candidate types:

- artifact candidate: stale chunk, wrong summary, ignored tool result;
- step candidate: retriever, summarizer, final LLM call, validator;
- omission candidate: correct evidence missing from prompt;
- instrumentation candidate: trace missing needed artifact.

Candidate score features:

- direct support for bad claim;
- contradiction by fresher or higher-authority evidence;
- position on generated-from path to final output;
- failed invariant count and severity;
- omission/ignored-evidence signal;
- authority/freshness metadata;
- uncertainty penalty for semantic-only edges.

Acceptance:

- candidate explanations are feature-transparent;
- no candidate can rank first without either path evidence or check evidence.

### Stage 9: Localize And Judge

Use a localizer modeled after AgentRx's judge but adapted to Origo's output
orientation.

The judge input is not the whole raw trace. It is an evidence pack:

```text
failed claim/action
candidate cards
minimal graph paths
failed checks
supporting snippets
contradicting snippets
omitted evidence
trace uncertainty notes
```

Output:

- selected culprit candidates;
- failure category;
- confidence and uncertainty;
- short explanation tied to artifacts.

Acceptance:

- judge output must be machine-parseable JSON;
- judge cannot introduce uncited evidence;
- judge can answer "insufficient trace data".

### Stage 10: Report

Markdown and JSON reports should include:

- bad output and expected output;
- culprit cards;
- traceback path;
- exact snippets;
- ignored or omitted evidence;
- failed checks;
- confidence and uncertainty;
- suggested fixes;
- trace debuggability issues.

## 8. Agents Required In The Product

"Agents" here means analyzer agents/components, not necessarily autonomous
background workers.

Required v1 analyzer agents:

- IR normalizer: deterministic mapping plus optional LLM fallback for weird logs.
- Claim/action extractor: turns final output into analyzable targets.
- Evidence matcher: exact, structured, semantic support/contradiction.
- Static invariant generator: optional, policy/tool-schema driven.
- Dynamic invariant generator: optional, trajectory-prefix driven.
- Check runner: deterministic, Python, and LLM-judge checks.
- Root-cause localizer: ranks candidates from evidence packs.
- Report writer: creates human and machine-readable culprit cards.

Autonomous Codex agents should implement these as separate modules with strict
file ownership. They are build agents, not the runtime product architecture.

## 9. Proposed Repository Structure

```text
origo/
  ir/
    models.py
    normalize.py
    artifact_extractor.py
  importers/
    local_json.py
    openinference.py
    phoenix.py
    langfuse.py
    traceroot.py
  failure/
    spec.py
    target.py
  extraction/
    claims.py
    actions.py
  provenance/
    graph.py
    structural_edges.py
    inclusion_edges.py
    dataflow_edges.py
    semantic_edges.py
    omission_edges.py
    slicing.py
  invariants/
    models.py
    library.py
    static_generator.py
    dynamic_generator.py
    checker.py
  analysis/
    evidence_pack.py
    candidates.py
    ranker.py
    localizer.py
  reports/
    cards.py
    markdown.py
    json_report.py
  runs/
    writer.py
  cli.py
tests/
examples/
docs/
```

## 10. Milestones

### M0: Admit Scaffold Status

Update README and docs to say current implementation is a foundation scaffold.
Keep tests, but do not present the canned examples as full tracing.

Done when:

- README says Origo is pre-alpha;
- current toy examples are named fixtures;
- `docs/technical-design-v1.md` exists.

### M1: Real Trajectory IR And Run Artifacts

Implement `origo.ir` and `origo.runs`.

Done when:

- `origo explain` writes a run directory;
- local JSON imports into `TrajectoryIR`;
- every stage writes a JSON artifact;
- tests assert run artifacts exist.

### M2: Artifact Extraction

Replace span-level matching with artifact-level extraction.

Done when:

- final output, tool results, retrieval chunks, prompts, and summaries are
  separate artifacts;
- reports cite artifact IDs and span IDs;
- tests fail if only span IDs are available but artifact text is missing.

### M3: OpenInference Importer

Implement serious trace import before adding more toy examples.

Done when:

- OTLP/OpenInference JSON imports into IR;
- retrieval documents, input/output, tool calls/results are extracted;
- an example generated from a real instrumented mini-agent can be analyzed.

### M4: Validation Log And Built-In Checks

Implement `invariants.library` and `invariants.checker`.

Done when:

- validation log is produced for every report;
- stale retrieval, ignored tool output, unsupported claim, wrong tool argument,
  summary corruption, memory conflict, and validator gap have at least one check;
- reports cite failed check IDs.

### M5: Provenance Graph V2

Replace current graph with layered provenance edges.

Done when:

- parent-child edges are separate from dataflow edges;
- prompt inclusion can be proven;
- semantic edges cite exact snippets and methods;
- minimal subgraph extraction uses failed claim/action as the sink.

### M6: Localizer/Judge

Add optional LLM localizer over evidence packs.

Done when:

- deterministic mode works without LLM;
- LLM mode only sees evidence packs, not raw giant traces;
- judge output is JSON and cannot add uncited claims.

### M7: Langfuse/Phoenix Import

Add adapters for exported traces and eval annotations.

Done when:

- Langfuse trace/observation/score export maps into IR/artifacts/checks;
- Phoenix span JSON or trace dataset maps into IR/artifacts/checks;
- imported scores can influence candidate ranking.

### M8: Benchmark And Baselines

Build a small but honest benchmark.

Done when:

- examples include real-ish traces, not only hand-crafted culprit labels;
- baselines include final-span-only, whole-trace LLM judge, and graph-only ranker;
- metrics include top-1 culprit, evidence recall, false attribution rate, and
  insufficient-data detection.

## 11. Acceptance Tests For "Actually Tracing"

Origo is not truly tracing until these pass:

- Removing user-provided expected culprit IDs does not break diagnosis.
- Removing final-output text from intermediate spans prevents false certainty.
- A stale retrieved chunk is found through generated-from/support edges, not
  fixture-specific IDs.
- A correct tool result is detected as ignored only if it existed before final
  generation and was either omitted from prompt context or contradicted in output.
- A wrong final claim can be traced to a summary artifact, not merely the final
  LLM span.
- The report includes validation log IDs and evidence snippets.
- The system can say "insufficient trace data" when prompt contents or tool
  results are missing.

## 12. Autonomous Codex Work Plan

Use one coordinator and independent workers. Every worker must be told:

> You are not alone in the codebase; do not revert others' edits; edit only the
> allowed files.

Recommended agents:

- Coordinator: CLI, run artifact writer, integration tests.
- IR worker: `origo/ir`, local importer, schema tests.
- OpenInference worker: `origo/importers/openinference.py`, importer fixtures.
- Artifact worker: artifact extraction from IR.
- Provenance worker: structural, inclusion, dataflow, semantic, omission edges.
- Invariants worker: invariant schema, built-in library, checker, validation log.
- Analysis worker: candidates, ranker, evidence pack, localizer interface.
- Reports worker: culprit cards, Markdown, JSON, terminal output.

Order matters:

1. IR and run artifacts first.
2. Artifact extraction second.
3. Importers and provenance can proceed in parallel after IR stabilizes.
4. Invariants/checker can proceed once artifacts have stable IDs.
5. Reports should lag behind the validation log and candidates.

## 13. Risks And Guardrails

Risk: Origo becomes another dashboard.

Guardrail: no web UI until CLI reports are compelling on real traces.

Risk: semantic matching hallucinates.

Guardrail: every semantic edge must record method, snippets, and confidence.

Risk: the LLM judge reads the whole trace and invents a story.

Guardrail: judge only reads evidence packs assembled from graph/check outputs.

Risk: parent-child spans are mistaken for causality.

Guardrail: reports must distinguish structural path from evidence path.

Risk: benchmarks reward positional shortcuts.

Guardrail: include shuffled/out-of-order traces and non-final culprit examples.

## 14. Sources Inspected

- AgentRx repository: https://github.com/microsoft/AgentRx
- Phoenix repository: https://github.com/arize-ai/phoenix
- Langfuse repository: https://github.com/langfuse/langfuse
- TraceRoot repository: https://github.com/traceroot-ai/traceroot
- Original Origo/AI Traceback design doc:
  `/Users/rohitsandadi/Downloads/ai_traceback_design_doc.md`

Key local files inspected:

- `/tmp/origo-research/AgentRx/run.py`
- `/tmp/origo-research/AgentRx/src/ir/trajectory_ir.py`
- `/tmp/origo-research/AgentRx/src/invariants/static_invariant_generator.py`
- `/tmp/origo-research/AgentRx/src/invariants/dynamic_invariant_generator.py`
- `/tmp/origo-research/AgentRx/src/invariants/checker.py`
- `/tmp/origo-research/AgentRx/src/judge/judge.py`
- `/tmp/origo-research/phoenix/src/phoenix/trace/schemas.py`
- `/tmp/origo-research/phoenix/src/phoenix/trace/otel.py`
- `/tmp/origo-research/phoenix/src/phoenix/db/insertion/span.py`
- `/tmp/origo-research/phoenix/packages/phoenix-evals/src/phoenix/evals/metrics/tool_response_handling.py`
- `/tmp/origo-research/langfuse/worker/src/services/IngestionService/index.ts`
- `/tmp/origo-research/langfuse/packages/shared/src/server/repositories/definitions.ts`
- `/tmp/origo-research/traceroot/backend/worker/otel_transform.py`
- `/tmp/origo-research/traceroot/backend/worker/ingest_tasks.py`
- `/tmp/origo-research/traceroot/docs/ai-agent/root-cause-analysis.mdx`
