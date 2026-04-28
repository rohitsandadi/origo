from __future__ import annotations

from origo.invariants.models import Invariant


def load_builtin_static_invariants() -> list[Invariant]:
    """Return Origo's deterministic built-in invariant library."""

    return [
        Invariant(
            id="builtin:stale_retrieval",
            name="Stale retrieved evidence must not determine final factual claims",
            scope="static",
            target_kinds=["retrieved_chunk", "summary", "final_output"],
            trigger="retrieved evidence supports bad output while fresher expected evidence contradicts it",
            check_type="structured",
            assertion=(
                "When retrieved evidence and fresher tool or expected evidence conflict, final output must "
                "prefer the fresher evidence or explicitly surface the conflict."
            ),
            metadata={"failure_mode": "stale_retrieval"},
        ),
        Invariant(
            id="builtin:ignored_evidence",
            name="Available expected evidence must be represented in final synthesis",
            scope="static",
            target_kinds=["tool_result", "retrieved_chunk", "summary", "final_output"],
            trigger="expected evidence exists before final output but is omitted or contradicted",
            check_type="structured",
            assertion=(
                "Correct evidence available before final generation must either appear in the final context "
                "or be reflected by the final answer."
            ),
            metadata={"failure_mode": "ignored_tool_output"},
        ),
        Invariant(
            id="builtin:unsupported_claim",
            name="Final claims require supporting evidence",
            scope="static",
            target_kinds=["final_output", "retrieved_chunk", "tool_result"],
            trigger="final claim has no supporting included evidence",
            check_type="structured",
            assertion="Every factual final claim should be supported by included retrieval, tool, memory, or state evidence.",
            metadata={"failure_mode": "unsupported_claim"},
        ),
        Invariant(
            id="builtin:wrong_tool_argument",
            name="Tool arguments must match the user request and available context",
            scope="static",
            target_kinds=["tool_call", "tool_result"],
            trigger="tool call arguments conflict with user request or prior state",
            check_type="structured",
            assertion="Tool call arguments should preserve the entities, dates, quantities, and scope requested by the user.",
            metadata={"failure_mode": "wrong_tool_argument"},
        ),
        Invariant(
            id="builtin:validator_gap",
            name="Validators must check the relevant failure surface",
            scope="static",
            target_kinds=["validator", "final_output"],
            trigger="validator ran but did not cover the failure mode",
            check_type="structured",
            assertion="A validator should cover the factual/tool-use failure mode relevant to the final output.",
            metadata={"failure_mode": "validator_gap"},
        ),
    ]


def load_builtin_dynamic_invariants() -> list[Invariant]:
    """Dynamic invariant generation is not implemented yet; persist an explicit empty set."""

    return []
