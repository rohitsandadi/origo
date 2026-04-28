from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from origo.analysis.artifact_candidates import ArtifactCulpritCandidate, rank_artifact_candidates
from origo.analysis.evidence_pack import EvidencePack, build_evidence_pack
from origo.extraction.actions import extract_actions
from origo.extraction.claims import extract_claims
from origo.failure.target import FailureTarget, select_failure_target
from origo.invariants.checker import run_builtin_checks
from origo.invariants.library import load_builtin_dynamic_invariants, load_builtin_static_invariants
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
    culprit_candidates: list[ArtifactCulpritCandidate]
    evidence_pack: EvidencePack
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
    static_invariants = load_builtin_static_invariants()
    dynamic_invariants = load_builtin_dynamic_invariants()
    report = analyze_traceback(trace, failure)
    validation_log = run_builtin_checks(trace, failure, artifacts, report.graph)
    culprit_candidates = rank_artifact_candidates(artifacts, provenance_graph, validation_log)
    evidence_pack = build_evidence_pack(
        failure_target=failure_target,
        claims=claims,
        actions=actions,
        candidates=culprit_candidates,
        validation_log=validation_log,
    )
    _attach_failed_checks(report, validation_log)
    _attach_artifact_candidates(report, culprit_candidates, validation_log)
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
        writer.write_json("invariants_static", static_invariants)
        writer.write_json("invariants_dynamic", dynamic_invariants)
        writer.write_json("validation_log", validation_log)
        writer.write_json("culprit_candidates", culprit_candidates)
        writer.write_json("evidence_pack", evidence_pack)
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
        culprit_candidates=culprit_candidates,
        evidence_pack=evidence_pack,
        run_dir=run_dir,
    )


def _attach_failed_checks(report: TracebackReport, validation_log: list[CheckResult]) -> None:
    failed = [check for check in validation_log if check.status == "fail"]
    for card in report.cards:
        relevant_spans = {card.culprit_span_id, *card.ignored_evidence_span_ids}
        card.failed_check_ids = [
            check.id for check in failed if check.target_step_id in relevant_spans
        ]


def _attach_artifact_candidates(
    report: TracebackReport,
    candidates: list[ArtifactCulpritCandidate],
    validation_log: list[CheckResult],
) -> None:
    candidates_by_span = {
        candidate.span_id: candidate for candidate in candidates if candidate.span_id is not None
    }
    failed_checks = [check for check in validation_log if check.status == "fail"]
    for card in report.cards:
        if candidate := candidates_by_span.get(card.culprit_span_id):
            card.culprit_artifact_ids = [candidate.artifact_id]
            card.traceback_path = candidate.path
            card.failed_check_ids = _unique([*card.failed_check_ids, *candidate.failed_check_ids])
        ignored_artifacts = [
            check.target_artifact_id
            for check in failed_checks
            if check.target_step_id in card.ignored_evidence_span_ids and check.target_artifact_id is not None
        ]
        card.ignored_evidence_artifact_ids = _unique(ignored_artifacts)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
