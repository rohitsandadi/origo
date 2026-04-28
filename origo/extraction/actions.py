from __future__ import annotations

from typing import Any

from origo.ir.models import Artifact
from origo.schema.report import OutputAction


def extract_actions(artifacts: list[Artifact]) -> list[OutputAction]:
    """Extract structured final actions using deterministic heuristics."""

    actions: list[OutputAction] = []
    for artifact in artifacts:
        if artifact.kind != "final_output" or not isinstance(artifact.content, dict):
            continue
        action_type = artifact.content.get("action_type") or artifact.content.get("type")
        if not isinstance(action_type, str):
            continue
        arguments = artifact.content.get("arguments") or artifact.content.get("args") or {}
        if not isinstance(arguments, dict):
            arguments = {"value": arguments}
        actions.append(
            OutputAction(
                id=f"action:{artifact.id}",
                action_type=action_type,
                arguments=arguments,
                source_artifact_id=artifact.id,
                source_span_id=artifact.span_id,
                tool_name=_string_or_none(artifact.content.get("tool_name")),
                extraction_method="heuristic",
            )
        )
    return actions


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None
