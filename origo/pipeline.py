from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from origo.extraction.actions import extract_actions
from origo.extraction.claims import extract_claims
from origo.failure.target import FailureTarget, select_failure_target
from origo.invariants.checker import run_builtin_checks
from origo.invariants.models import CheckResult
from origo.ir.artifact_extractor import extract_artifacts
from origo.ir.models import Artifact, TrajectoryIR
from origo.ir.normalize import trace_to_trajectory_ir
from origo.provenance.graph import build_artifact_provenance_graph
from origo.reports.cards import analyze_traceback
from origo.reports.json_report import report_to_json
from origo.reports.markdown import render_markdown
from origo.runs.writer import RunArtifactWriter
from origo.schema.failure import FailureSpec
from origo.schema.graph import TraceGraph
from origo.schema.report import TracebackReport
from origo.schema.trace import TraceRun


@dataclass(frozen=True)
class AnalysisResult:
    report: TracebackReport
    trajectory_ir: TrajectoryIR
    artifacts: list[Artifact]
    failure_target: FailureTarget
    claims: list[object]
    actions: list[object]
    provenance_graph: TraceGraph
    validation_log: list[CheckResult]
    run_dir: Path | None = None


def analyze_with_artifacts(
    trace: TraceRun,
    failure: FailureSpec,
    run_root: str | Path | None = None,
) -> AnalysisResult:
    """Analyze a trace and optionally persist each auditable stage artifact."""

    trajectory_ir = trace_to_trajectory_ir(trace)
    artifacts = extract_artifacts(trajectory_ir)
    failure_target = select_failure_target(failure, artifacts)
    claims = extract_claims(failure_target)
    actions = extract_actions(artifacts)
    provenance_graph = build_artifact_provenance_graph(trajectory_ir, artifacts)
    report = analyze_traceback(trace, failure)
    validation_log = run_builtin_checks(trace, failure, artifacts, report.graph)
    _attach_failed_checks(report, validation_log)
    run_dir: Path | None = None

    if run_root is not None:
        writer = RunArtifactWriter(run_root, trace.run_id)
        writer.write_json("normalized_trace", trace)
        writer.write_json("failure_spec", failure)
        writer.write_json("failure_target", failure_target)
        writer.write_json("trajectory_ir", trajectory_ir)
        writer.write_json("artifacts", artifacts)
        writer.write_json("claims", claims)
        writer.write_json("actions", actions)
        writer.write_json("provenance_graph", provenance_graph)
        writer.write_json("validation_log", validation_log)
        writer.write_json("report", report_to_json(report))
        writer.write_text("report.md", render_markdown(report))
        run_dir = writer.run_dir

    return AnalysisResult(
        report=report,
        trajectory_ir=trajectory_ir,
        artifacts=artifacts,
        failure_target=failure_target,
        claims=claims,
        actions=actions,
        provenance_graph=provenance_graph,
        validation_log=validation_log,
        run_dir=run_dir,
    )


def _attach_failed_checks(report: TracebackReport, validation_log: list[CheckResult]) -> None:
    failed = [check for check in validation_log if check.status == "fail"]
    for card in report.cards:
        relevant_spans = {card.culprit_span_id, *card.ignored_evidence_span_ids}
        card.failed_check_ids = [
            check.id for check in failed if check.target_step_id in relevant_spans
        ]
