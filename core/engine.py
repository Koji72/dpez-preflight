"""
dPEZ Preflight — Main Analysis Engine
Orchestrates all analyzers and builds the final PrintabilityReport.
"""
import time
import os
import trimesh
import numpy as np
from typing import Optional
from core.models import (
    PrintabilityReport, MeshStats, Issue, Severity, PrinterProfile
)
from analyzers.manifold  import analyze_manifold
from analyzers.geometry  import analyze_wall_thickness, analyze_overhangs, analyze_floating_geometry
from analyzers.scale     import analyze_scale


# Score penalties per severity
SCORE_PENALTIES = {
    Severity.CRITICAL: 25,
    Severity.WARNING:  10,
    Severity.INFO:      2,
    Severity.OK:        0,
}


def analyze_stl(
    filepath: str,
    printer: PrinterProfile = PrinterProfile.BAMBU_X1C,
    attempt_repair: bool = False
) -> PrintabilityReport:
    """
    Run full analysis pipeline on an STL file.
    Returns a PrintabilityReport with all detected issues and scores.
    """
    t_start = time.perf_counter()

    filename = os.path.basename(filepath)
    file_size_kb = os.path.getsize(filepath) / 1024

    report = PrintabilityReport(
        filename=filename,
        file_size_kb=file_size_kb,
        printer=printer
    )

    # --- Load mesh ---
    try:
        mesh = trimesh.load(filepath, force='mesh')
    except Exception as e:
        report.issues.append(Issue(
            code="LOAD_FAILED",
            severity=Severity.CRITICAL,
            title="Failed to load STL file",
            description=f"Could not parse file: {str(e)[:120]}",
        ))
        report.score = 0
        report.verdict = "❌ File could not be loaded"
        report.analysis_time_ms = (time.perf_counter() - t_start) * 1000
        return report

    # --- Populate mesh stats ---
    stats = MeshStats(
        vertex_count=len(mesh.vertices),
        face_count=len(mesh.faces),
        edge_count=len(mesh.edges_unique) if hasattr(mesh, 'edges_unique') else 0,
        is_watertight=mesh.is_watertight,
        is_winding_consistent=mesh.is_winding_consistent,
        bounding_box=tuple(mesh.bounding_box.extents.tolist()),
    )
    
    try:
        stats.surface_area = float(mesh.area)
    except Exception:
        pass
    
    try:
        stats.volume = float(abs(mesh.volume)) if mesh.is_watertight else 0.0
    except Exception:
        pass
    
    try:
        components = trimesh.graph.connected_components(mesh.face_adjacency)
        stats.component_count = len(list(components))
    except Exception:
        stats.component_count = 1

    report.mesh_stats = stats

    # --- Run all analyzers ---
    all_issues = []
    all_issues += analyze_manifold(mesh)
    all_issues += analyze_wall_thickness(mesh, printer)
    all_issues += analyze_overhangs(mesh)
    all_issues += analyze_floating_geometry(mesh)
    all_issues += analyze_scale(mesh, printer)

    # Optional: auto-repair pass
    if attempt_repair:
        from core.repair import repair_mesh
        repaired_mesh, applied_fixes = repair_mesh(mesh)
        if applied_fixes:
            for fix in applied_fixes:
                all_issues.append(Issue(
                    code="AUTO_REPAIR_APPLIED",
                    severity=Severity.INFO,
                    title="Auto-repair applied",
                    description=fix,
                ))

    report.issues = all_issues

    # --- Calculate score ---
    score = 100
    for issue in all_issues:
        score -= SCORE_PENALTIES.get(issue.severity, 0)
    score = max(0, score)
    report.score = score

    # --- Verdict ---
    critical_count = len(report.critical_issues())
    warning_count  = len(report.warnings())

    if critical_count == 0 and score >= 80:
        report.ready_to_print = True
        report.verdict = f"✅ Ready to print  (score: {score}/100)"
    elif critical_count == 0:
        report.ready_to_print = True
        report.verdict = f"⚠️  Printable with warnings  (score: {score}/100)"
    else:
        report.ready_to_print = False
        report.verdict = f"❌ Not ready — {critical_count} critical issue(s)  (score: {score}/100)"

    report.analysis_time_ms = (time.perf_counter() - t_start) * 1000
    return report
