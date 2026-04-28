from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from origo.ir.models import Artifact
from origo.schema.failure import FailureSpec


class FailureTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    bad_output: str
    expected_output: str | None = None
    final_output_artifact_id: str | None = None
    final_output_span_id: str | None = None
    match_status: Literal["matched", "ambiguous", "missing_final_output", "unmatched"]
    uncertainty: str | None = None


def select_failure_target(failure: FailureSpec, artifacts: list[Artifact]) -> FailureTarget:
    final_artifacts = [artifact for artifact in artifacts if artifact.kind == "final_output"]
    candidate_artifacts = (
        [artifact for artifact in final_artifacts if artifact.span_id == failure.final_output_span_id]
        if failure.final_output_span_id
        else final_artifacts
    )

    if not candidate_artifacts:
        return FailureTarget(
            id=f"failure_target:{failure.failure_id}",
            bad_output=failure.bad_output,
            expected_output=failure.expected,
            match_status="missing_final_output",
            uncertainty="No final output artifact was available in the trace.",
        )

    matching_artifacts = [
        artifact
        for artifact in candidate_artifacts
        if artifact.text and _normalize(failure.bad_output) in _normalize(artifact.text)
    ]
    if len(matching_artifacts) == 1:
        artifact = matching_artifacts[0]
        return _target(failure, artifact, "matched")
    if len(matching_artifacts) > 1:
        artifact = matching_artifacts[0]
        return _target(
            failure,
            artifact,
            "ambiguous",
            "Multiple final output artifacts contained the bad output text.",
        )

    artifact = candidate_artifacts[0]
    return _target(
        failure,
        artifact,
        "unmatched",
        "A final output artifact was found, but it did not contain the exact bad output text.",
    )


def _target(
    failure: FailureSpec,
    artifact: Artifact,
    status: Literal["matched", "ambiguous", "missing_final_output", "unmatched"],
    uncertainty: str | None = None,
) -> FailureTarget:
    return FailureTarget(
        id=f"failure_target:{failure.failure_id}",
        bad_output=failure.bad_output,
        expected_output=failure.expected,
        final_output_artifact_id=artifact.id,
        final_output_span_id=artifact.span_id,
        match_status=status,
        uncertainty=uncertainty,
    )


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())
