from __future__ import annotations

from origo.schema.failure import FailureSpec
from origo.schema.report import OutputClaim
from origo.schema.trace import TraceRun
from origo.failure.target import FailureTarget


def extract_claims(target: FailureTarget) -> list[OutputClaim]:
    """Extract v1 claims from the selected failure target."""

    return [
        OutputClaim(
            id="claim:bad_output",
            text=target.bad_output,
            source_artifact_id=target.final_output_artifact_id,
            source_span_id=target.final_output_span_id,
            confidence=1.0,
            extraction_method="manual",
        )
    ]


def extract_bad_output_claim(trace: TraceRun, failure: FailureSpec) -> OutputClaim:
    """Extract the v0 claim: the final bad output as a single claim."""
    source_span_id = failure.final_output_span_id
    if source_span_id is None:
        final_span = trace.final_output_span()
        source_span_id = final_span.id if final_span is not None else ""

    return OutputClaim(
        id="claim:bad_output",
        text=failure.bad_output,
        source_span_id=source_span_id,
        confidence=1.0,
    )
