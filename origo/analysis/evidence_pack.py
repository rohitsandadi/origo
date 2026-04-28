from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from origo.analysis.artifact_candidates import ArtifactCulpritCandidate
from origo.failure.target import FailureTarget
from origo.invariants.models import CheckResult
from origo.schema.report import OutputAction, OutputClaim


class EvidencePack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    failure_target: FailureTarget
    claims: list[OutputClaim] = Field(default_factory=list)
    actions: list[OutputAction] = Field(default_factory=list)
    candidates: list[ArtifactCulpritCandidate] = Field(default_factory=list)
    failed_checks: list[CheckResult] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)


def build_evidence_pack(
    failure_target: FailureTarget,
    claims: list[OutputClaim],
    actions: list[OutputAction],
    candidates: list[ArtifactCulpritCandidate],
    validation_log: list[CheckResult],
) -> EvidencePack:
    failed_checks = [check for check in validation_log if check.status == "fail"]
    uncertainty_notes = [failure_target.uncertainty] if failure_target.uncertainty else []
    return EvidencePack(
        failure_target=failure_target,
        claims=claims,
        actions=actions,
        candidates=candidates,
        failed_checks=failed_checks,
        uncertainty_notes=uncertainty_notes,
    )
