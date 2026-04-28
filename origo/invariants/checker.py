from __future__ import annotations

import re

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
    provenance_graph: TraceGraph | None = None,
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
    if provenance_graph is not None:
        checks.extend(_unsupported_claim_checks(failure, artifacts, provenance_graph))
    checks.extend(_imported_score_checks(trace, artifact_ids))
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
                invariant_id="builtin:stale_retrieval",
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
                invariant_id="builtin:ignored_evidence",
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


def _unsupported_claim_checks(
    failure: FailureSpec,
    artifacts: list[Artifact],
    graph: TraceGraph,
) -> list[CheckResult]:
    if failure.failure_type != "unsupported_claim":
        return []

    final_artifact = next((artifact for artifact in artifacts if artifact.kind == "final_output"), None)
    if final_artifact is None:
        return []

    included_evidence = _included_evidence_artifacts(artifacts, graph, final_artifact.id)
    if not included_evidence:
        return []

    if any(_artifact_supports_claim(artifact, failure.bad_output) for artifact in included_evidence):
        return []

    return [
        CheckResult(
            id=f"check:unsupported_claim:{final_artifact.id}",
            invariant_id="builtin:unsupported_claim",
            check_name="final claim lacks support in included evidence",
            target_step_id=final_artifact.span_id,
            target_artifact_id=final_artifact.id,
            status="fail",
            failure_mode="unsupported_claim",
            explanation=(
                "The final output claim was generated from available context, but none of the included "
                "evidence artifacts support the claim text."
            ),
            evidence_refs=[final_artifact.id, *[artifact.id for artifact in included_evidence]],
            confidence=0.7,
        )
    ]


def _included_evidence_artifacts(
    artifacts: list[Artifact],
    graph: TraceGraph,
    final_artifact_id: str,
) -> list[Artifact]:
    final_node_id = f"artifact:{final_artifact_id}"
    evidence_kinds = {
        "retrieved_document",
        "retrieved_chunk",
        "tool_result",
        "memory_item",
        "summary",
        "state",
        "validator_result",
    }
    included: list[Artifact] = []
    for artifact in artifacts:
        if artifact.id == final_artifact_id or artifact.kind not in evidence_kinds:
            continue
        path = graph.shortest_path(f"artifact:{artifact.id}", final_node_id, kinds={"generated_from"})
        if path is not None:
            included.append(artifact)
    return included


def _artifact_supports_claim(artifact: Artifact, claim: str) -> bool:
    if artifact.text is None:
        return False

    artifact_text = _normalize_text(artifact.text)
    claim_text = _normalize_text(claim)
    if not artifact_text or not claim_text:
        return False
    if claim_text in artifact_text:
        return True
    if len(artifact_text) >= 12 and artifact_text in claim_text:
        return True

    claim_numbers = set(_numbers(claim_text))
    if claim_numbers:
        return bool(claim_numbers & set(_numbers(artifact_text))) and _has_context_overlap(claim_text, artifact_text)

    return False


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _numbers(value: str) -> list[str]:
    return re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", value)


def _has_context_overlap(claim_text: str, artifact_text: str) -> bool:
    claim_words = {word for word in re.findall(r"[a-zA-Z][a-zA-Z_'-]*", claim_text) if len(word) > 3}
    if not claim_words:
        return True
    artifact_words = set(re.findall(r"[a-zA-Z][a-zA-Z_'-]*", artifact_text))
    return bool(claim_words & artifact_words)


def _imported_score_checks(trace: TraceRun, artifact_ids: set[str]) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for span in trace.spans:
        scores = span.metadata.get("langfuse_scores") or span.metadata.get("phoenix_scores") or []
        if not isinstance(scores, list):
            continue
        for index, score in enumerate(scores):
            if not isinstance(score, dict):
                continue
            value = score.get("value")
            if not isinstance(value, int | float) or value > 0:
                continue
            score_id = str(score.get("id") or f"{span.id}:{index}")
            name = str(score.get("name") or "imported_score")
            failure_mode = _failure_mode_from_score_name(name)
            checks.append(
                CheckResult(
                    id=f"imported-score:{score_id}",
                    check_name=f"imported score failed: {name}",
                    target_step_id=span.id,
                    target_artifact_id=_artifact_id(span.id, artifact_ids),
                    status="fail",
                    failure_mode=failure_mode,
                    explanation=str(score.get("comment") or f"Imported score `{name}` marked this observation as failing."),
                    evidence_refs=[_artifact_id(span.id, artifact_ids)],
                    confidence=0.8,
                )
            )
    return checks


def _failure_mode_from_score_name(name: str) -> str:
    normalized = name.lower()
    if "tool_response" in normalized or "tool response" in normalized:
        return "ignored_tool_output"
    if "faithfulness" in normalized or "hallucination" in normalized:
        return "unsupported_claim"
    if "tool_invocation" in normalized or "tool invocation" in normalized:
        return "wrong_tool_argument"
    return "other"


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
