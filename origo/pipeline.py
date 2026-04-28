from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from origo.ir.artifact_extractor import extract_artifacts
from origo.ir.models import Artifact, TrajectoryIR
from origo.ir.normalize import trace_to_trajectory_ir
from origo.reports.cards import analyze_traceback
from origo.reports.json_report import report_to_json
from origo.reports.markdown import render_markdown
from origo.runs.writer import RunArtifactWriter
from origo.schema.failure import FailureSpec
from origo.schema.report import TracebackReport
from origo.schema.trace import TraceRun


@dataclass(frozen=True)
class AnalysisResult:
    report: TracebackReport
    trajectory_ir: TrajectoryIR
    artifacts: list[Artifact]
    run_dir: Path | None = None


def analyze_with_artifacts(
    trace: TraceRun,
    failure: FailureSpec,
    run_root: str | Path | None = None,
) -> AnalysisResult:
    """Analyze a trace and optionally persist each auditable stage artifact."""

    trajectory_ir = trace_to_trajectory_ir(trace)
    artifacts = extract_artifacts(trajectory_ir)
    report = analyze_traceback(trace, failure)
    run_dir: Path | None = None

    if run_root is not None:
        writer = RunArtifactWriter(run_root, trace.run_id)
        writer.write_json("normalized_trace", trace)
        writer.write_json("failure_spec", failure)
        writer.write_json("trajectory_ir", trajectory_ir)
        writer.write_json("artifacts", artifacts)
        writer.write_json("report", report_to_json(report))
        writer.write_text("report.md", render_markdown(report))
        run_dir = writer.run_dir

    return AnalysisResult(
        report=report,
        trajectory_ir=trajectory_ir,
        artifacts=artifacts,
        run_dir=run_dir,
    )
