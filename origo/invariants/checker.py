from __future__ import annotations

from origo.analysis.evidence_matcher import match_evidence
from origo.invariants.models import CheckResult
from origo.ir.models import Artifact
from origo.schema.failure import FailureSpec
from origo.schema.graph import TraceGraph
from origo.schema.trace import TraceRun


def run_builtin_checks(
    trace: TraceRun,
    failure: FailureSpec,
    artifacts: list[Artifact],
    graph: TraceGraph | None,
) -> list[CheckResult]:
    """Run deterministic v1 checks and return an auditable validation log."""

    artifact_ids = {artifact.id for artifact in artifacts}
    matches = match_evidence(trace, failure)
    bad_span_ids = {match.span_id for match in matches.bad_output}
    expected_span_ids = {match.span_id for match in matches.expected_output}

    checks: list[CheckResult] = []
    checks.extend(_stale_retrieval_checks(trace, failure, artifact_ids, bad_span_ids, expected_span_ids))
    if graph is not None:
        checks.extend(_ignored_evidence_checks(trace, artifact_ids, graph))
    return _unique_checks(checks)


def _stale_retrieval_checks(
    trace: TraceRun,
    failure: FailureSpec,
    artifact_ids: set[str],
    bad_span_ids: set[str],
    expected_span_ids: set[str],
) -> list[CheckResult]:
    if failure.failure_type != "stale_retrieval" or not expected_span_ids:
        return []

    checks: list[CheckResult] = []
    for span_id in sorted(bad_span_ids):
        span = trace.get_span(span_id)
        if span.kind != "retrieved_chunk":
            continue

        target_artifact_id = _artifact_id(span_id, artifact_ids)
        evidence_refs = [target_artifact_id, *[_artifact_id(expected_id, artifact_ids) for expected_id in sorted(expected_span_ids)]]
        checks.append(
            CheckResult(
                id=f"check:stale_retrieval:{span_id}",
                check_name="stale retrieved evidence supports bad output",
                target_step_id=span_id,
                target_artifact_id=target_artifact_id,
                status="fail",
                failure_mode="stale_retrieval",
                explanation=(
                    f"Retrieved evidence `{span_id}` supports the bad output while newer or expected "
                    "evidence contradicts it."
                ),
                evidence_refs=evidence_refs,
                confidence=0.9,
            )
        )
    return checks


def _ignored_evidence_checks(
    trace: TraceRun,
    artifact_ids: set[str],
    graph: TraceGraph,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for edge in graph.edges:
        if edge.kind not in {"omitted_from_final_prompt", "ignored_by_final_output"}:
            continue
        span_id = edge.source.removeprefix("span:")
        span = trace.get_span(span_id)
        failure_mode = "ignored_tool_output" if span.kind == "tool_result" else edge.kind
        target_artifact_id = _artifact_id(span_id, artifact_ids)
        checks.append(
            CheckResult(
                id=f"check:ignored_evidence:{span_id}",
                check_name="expected evidence was omitted or ignored",
                target_step_id=span_id,
                target_artifact_id=target_artifact_id,
                status="fail",
                failure_mode=failure_mode,
                explanation=str(
                    edge.metadata.get("issue")
                    or "Correct evidence existed before the final answer but was not reflected in it."
                ),
                evidence_refs=[target_artifact_id, *edge.evidence],
                confidence=edge.confidence,
            )
        )
    return checks


def _artifact_id(span_id: str, artifact_ids: set[str]) -> str:
    output_id = f"{span_id}.output"
    if output_id in artifact_ids:
        return output_id
    input_id = f"{span_id}.input"
    if input_id in artifact_ids:
        return input_id
    return output_id


def _unique_checks(checks: list[CheckResult]) -> list[CheckResult]:
    result: list[CheckResult] = []
    seen: set[str] = set()
    for check in checks:
        if check.id in seen:
            continue
        seen.add(check.id)
        result.append(check)
    return result
