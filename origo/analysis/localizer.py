from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from origo.analysis.evidence_pack import EvidencePack


class LocalizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_candidate_artifact_ids: list[str] = Field(default_factory=list)
    failure_category: str | None = None
    confidence: float = 0.0
    explanation: str
    uncertainty: str | None = None
    insufficient_data: bool = False


def localize_from_evidence_pack(evidence_pack: EvidencePack) -> LocalizationResult:
    if not evidence_pack.candidates:
        return LocalizationResult(
            explanation="No culprit candidates were produced from the available trace evidence.",
            uncertainty="No culprit candidates were produced. The trace may be missing prompts, tool results, or retrieval evidence.",
            insufficient_data=True,
        )

    top = evidence_pack.candidates[0]
    category = top.failure_modes[0] if top.failure_modes else None
    return LocalizationResult(
        selected_candidate_artifact_ids=[top.artifact_id],
        failure_category=category,
        confidence=top.score,
        explanation=_explanation(top.artifact_id, top.reasons),
        uncertainty=None,
        insufficient_data=False,
    )


def _explanation(artifact_id: str, reasons: list[str]) -> str:
    if not reasons:
        return f"`{artifact_id}` is the top-ranked culprit candidate."
    return f"`{artifact_id}` is the top-ranked culprit candidate: {reasons[0]}"
