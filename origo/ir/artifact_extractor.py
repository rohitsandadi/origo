from __future__ import annotations

import json
from typing import Any

from origo.ir.models import Artifact, ArtifactKind, TrajectoryIR, TrajectoryStep, TrajectorySubstep


_OUTPUT_ARTIFACT_KINDS: dict[str, ArtifactKind] = {
    "user_input": "message",
    "system_prompt": "prompt",
    "prompt_assembly": "prompt",
    "retrieved_chunk": "retrieved_chunk",
    "tool_call": "tool_call",
    "tool_result": "tool_result",
    "memory_read": "memory_item",
    "memory_write": "memory_item",
    "context_summary": "summary",
    "state_update": "state",
    "validator": "validator_result",
    "final_output": "final_output",
}


def extract_artifacts(ir: TrajectoryIR) -> list[Artifact]:
    """Extract artifact-level evidence units from a trajectory IR."""

    span_ids = {step.span_id for step in ir.steps if step.span_id is not None}
    artifact_by_id: dict[str, Artifact] = {}

    for step in ir.steps:
        for substep in step.substeps:
            for artifact_id in substep.artifact_ids:
                artifact_by_id[artifact_id] = _artifact_from_substep(step, substep, artifact_id, span_ids)

    for artifact in artifact_by_id.values():
        for input_artifact_id in artifact.metadata.get("input_artifact_ids", []):
            input_artifact = artifact_by_id.get(input_artifact_id)
            if input_artifact is not None and artifact.id not in input_artifact.included_in_artifact_ids:
                input_artifact.included_in_artifact_ids.append(artifact.id)

    return list(artifact_by_id.values())


def _artifact_from_substep(
    step: TrajectoryStep,
    substep: TrajectorySubstep,
    artifact_id: str,
    span_ids: set[str],
) -> Artifact:
    field_name = str(substep.metadata.get("field") or artifact_id.rsplit(".", 1)[-1])
    input_artifact_ids = _input_artifact_ids(step, field_name, span_ids)
    metadata = {
        **substep.metadata,
        "step_index": step.index,
        "step_kind": step.kind,
    }
    if input_artifact_ids:
        metadata["input_artifact_ids"] = input_artifact_ids

    return Artifact(
        id=artifact_id,
        kind=_artifact_kind(step.kind, field_name),
        span_id=step.span_id,
        content=substep.content,
        text=_textify(substep.content),
        created_at_step=step.index,
        metadata=metadata,
    )


def _artifact_kind(step_kind: str, field_name: str) -> ArtifactKind:
    if field_name == "input":
        if step_kind in {"prompt_assembly", "llm_call", "final_output"}:
            return "prompt"
        if step_kind == "tool_call":
            return "tool_call"
        return "message"
    return _OUTPUT_ARTIFACT_KINDS.get(step_kind, "message")


def _input_artifact_ids(step: TrajectoryStep, field_name: str, span_ids: set[str]) -> list[str]:
    if field_name != "output":
        return []

    refs: list[str] = []
    for substep in step.substeps:
        if substep.metadata.get("field") == "input":
            refs.extend(_span_refs(substep.content, span_ids))
    return [f"{span_id}.output" for span_id in refs]


def _span_refs(value: Any, span_ids: set[str]) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith("_span_id") and isinstance(child, str) and child in span_ids:
                refs.append(child)
            elif key.endswith("_span_ids") and isinstance(child, list):
                refs.extend(item for item in child if isinstance(item, str) and item in span_ids)
            else:
                refs.extend(_span_refs(child, span_ids))
    elif isinstance(value, list):
        for child in value:
            refs.extend(_span_refs(child, span_ids))
    return refs


def _textify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)
