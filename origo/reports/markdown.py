from __future__ import annotations

from origo.schema.report import TracebackReport


def render_markdown(report: TracebackReport) -> str:
    lines = [
        "# Origo Traceback Report",
        "",
        "## Bad output",
        "",
        f"> {report.bad_output}",
    ]
    if report.expected:
        lines.extend(["", "Expected:", "", f"> {report.expected}"])

    if not report.cards:
        lines.extend(["", "## Culprit cards", "", "No culprit candidates were found."])
        return "\n".join(lines).rstrip() + "\n"

    for index, card in enumerate(report.cards, start=1):
        lines.extend(
            [
                "",
                f"## Culprit card {index}: {card.title}",
                "",
                f"Confidence: {card.confidence:.2f}",
                "",
                f"Culprit: `{card.culprit_span_id}`",
                "",
                f"Snippet: {card.culprit_snippet}",
            ]
        )
        if card.path:
            lines.extend(["", "Path:", ""])
            lines.extend(f"- `{span_id}`" for span_id in card.path)
        if card.why_suspicious:
            lines.extend(["", "Why suspicious:", ""])
            lines.extend(f"- {reason}" for reason in card.why_suspicious)
        if card.ignored_evidence:
            lines.extend(["", "Ignored evidence:", ""])
            for evidence in card.ignored_evidence:
                lines.append(f"- `{evidence.span_id}`: {evidence.snippet}")
                lines.append(f"  - {evidence.issue}")
        if card.failure_modes:
            lines.extend(["", "Failure modes:", ""])
            lines.extend(f"- `{mode}`" for mode in card.failure_modes)
        if card.suggested_fixes:
            lines.extend(["", "Suggested fixes:", ""])
            lines.extend(f"- {fix}" for fix in card.suggested_fixes)

    return "\n".join(lines).rstrip() + "\n"
