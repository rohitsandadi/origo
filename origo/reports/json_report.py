from __future__ import annotations

from typing import Any

from origo.schema.report import TracebackReport


def report_to_json(report: TracebackReport) -> dict[str, Any]:
    return report.model_dump(mode="json")
