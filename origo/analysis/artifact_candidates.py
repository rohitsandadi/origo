from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from origo.invariants.models import CheckResult
from origo.ir.models import Artifact
from origo.schema.graph import TraceGraph


class ArtifactCulpritCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    span_id: str | None = None
    score: float
    reasons: list[str] = Field(default_factory=list)
    failed_check_ids: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    path: list[str] = Field(default_factory=list)


def rank_artifact_candidates(
    artifacts: list[Artifact],
    graph: TraceGraph,
    validation_log: list[CheckResult],
) -> list[ArtifactCulpritCandidate]:
    artifact_by_id = {artifact.id: artifact for artifact in artifacts}
    final_artifact_id = _final_artifact_id(artifacts)
    failed_checks = [check for check in validation_log if check.status == "fail"]
    candidates: list[ArtifactCulpritCandidate] = []

    for check in failed_checks:
        if check.target_artifact_id is None:
            continue
        artifact = artifact_by_id.get(check.target_artifact_id)
        if artifact is None:
            continue
        if check.failure_mode == "ignored_tool_output":
            continue

        path = _artifact_path(graph, check.target_artifact_id, final_artifact_id)
        score = 0.5
        reasons = [check.explanation]
        if path:
            score += 0.25
            reasons.append("artifact has provenance path to final output")
        if check.failure_mode:
            score += 0.1

        candidates.append(
            ArtifactCulpritCandidate(
                artifact_id=artifact.id,
                span_id=artifact.span_id,
                score=round(min(score, 0.99), 4),
                reasons=reasons,
                failed_check_ids=[check.id],
                failure_modes=[check.failure_mode] if check.failure_mode else [],
                evidence_refs=check.evidence_refs,
                path=path,
            )
        )

    return sorted(candidates, key=lambda candidate: (-candidate.score, candidate.artifact_id))


def _final_artifact_id(artifacts: list[Artifact]) -> str | None:
    for artifact in artifacts:
        if artifact.kind == "final_output":
            return artifact.id
    return None


def _artifact_path(graph: TraceGraph, source_artifact_id: str, final_artifact_id: str | None) -> list[str]:
    if final_artifact_id is None:
        return []
    source = f"artifact:{source_artifact_id}"
    target = f"artifact:{final_artifact_id}"
    return graph.shortest_path(source, target, kinds={"generated_from"}) or []
