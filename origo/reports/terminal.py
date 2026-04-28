from __future__ import annotations

from origo.reports.markdown import render_markdown
from origo.schema.report import TracebackReport


def render_terminal(report: TracebackReport) -> str:
    return render_markdown(report)
