from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from origo.schema.failure import FailureSpec
from origo.schema.trace import TraceRun, TraceSpan


class SpanEvidenceMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    span_id: str
    snippets: list[str] = Field(default_factory=list)
    matched_values: list[str] = Field(default_factory=list)
    matched_fields: list[str] = Field(default_factory=list)


class EvidenceMatches(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bad_output: list[SpanEvidenceMatch] = Field(default_factory=list)
    expected_output: list[SpanEvidenceMatch] = Field(default_factory=list)


def match_evidence(trace: TraceRun, failure: FailureSpec) -> EvidenceMatches:
    return EvidenceMatches(
        bad_output=_match_target(trace, failure.bad_output),
        expected_output=_match_target(trace, failure.expected) if failure.expected else [],
    )


def _match_target(trace: TraceRun, target: str) -> list[SpanEvidenceMatch]:
    target_text = _normalize_text(target)
    target_numbers = _numbers(target)
    target_phrases = _candidate_phrases(target)

    matches: list[SpanEvidenceMatch] = []
    for span in trace.spans:
        leaves = list(_walk_leaves({"input": span.input, "output": span.output}))
        snippets: list[str] = []
        values: list[str] = []
        fields: list[str] = []

        for path, value in leaves:
            value_text = _leaf_text(value)
            normalized_value = _normalize_text(value_text)
            leaf_numbers = _numbers(value_text)

            if target_text and (
                target_text in normalized_value
                or (len(normalized_value) >= 12 and normalized_value in target_text)
            ):
                snippets.append(value_text)
                fields.append(path)

            shared_numbers = [number for number in target_numbers if number in leaf_numbers]
            if shared_numbers and (
                _is_number_only(normalized_value) or _has_context_overlap(target_phrases, f"{path} {normalized_value}")
            ):
                snippets.append(value_text)
                fields.append(path)
                values.extend(shared_numbers)

        if snippets or values:
            matches.append(
                SpanEvidenceMatch(
                    span_id=span.id,
                    snippets=_unique(snippets),
                    matched_values=_unique(values),
                    matched_fields=_unique(fields),
                )
            )

    return matches


def _walk_leaves(value: Any, path: str = "") -> list[tuple[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        leaves: list[tuple[str, Any]] = []
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            leaves.extend(_walk_leaves(child, child_path))
        return leaves
    if isinstance(value, list | tuple | set):
        leaves = []
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]" if path else f"[{index}]"
            leaves.extend(_walk_leaves(child, child_path))
        return leaves
    return [(path, value)]


def _leaf_text(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _numbers(value: str) -> list[str]:
    return re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", value)


def _is_number_only(value: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", value))


def _candidate_phrases(value: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z_'-]*", value.lower())
    return {word for word in words if len(word) > 3}


def _has_context_overlap(target_phrases: set[str], normalized_value: str) -> bool:
    if not target_phrases:
        return True
    value_words = set(re.findall(r"[a-zA-Z][a-zA-Z_'-]*", normalized_value))
    return bool(target_phrases & value_words)


def _unique(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
