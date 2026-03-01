"""
dPEZ Preflight — JSON Reporter
Structured output for API integration and pipeline use.
"""
import json
from core.models import PrintabilityReport


def report_to_dict(report: PrintabilityReport) -> dict:
    """Convert report to a clean JSON-serializable dict."""
    stats = report.mesh_stats
    bb = stats.bounding_box or [0, 0, 0]
    
    return {
        "dpez_version": "0.1.0",
        "file": {
            "name": report.filename,
            "size_kb": round(report.file_size_kb, 2),
        },
        "printer": report.printer.value,
        "result": {
            "score": report.score,
            "ready_to_print": report.ready_to_print,
            "verdict": report.verdict,
            "critical_count": len(report.critical_issues()),
            "warning_count": len(report.warnings()),
            "auto_fixable_count": len(report.auto_fixable_issues()),
            "analysis_time_ms": round(report.analysis_time_ms, 1),
        },
        "mesh": {
            "vertices": stats.vertex_count,
            "faces": stats.face_count,
            "edges": stats.edge_count,
            "volume_mm3": round(stats.volume, 3),
            "surface_area_mm2": round(stats.surface_area, 3),
            "dimensions_mm": {
                "x": round(bb[0], 2),
                "y": round(bb[1], 2),
                "z": round(bb[2], 2),
            },
            "watertight": stats.is_watertight,
            "winding_consistent": stats.is_winding_consistent,
            "component_count": stats.component_count,
        },
        "issues": [
            {
                "code": i.code,
                "severity": i.severity.value,
                "title": i.title,
                "description": i.description,
                "affected_count": i.affected_count,
                "auto_fixable": i.auto_fixable,
                "fix": i.fix_description,
                "technical_detail": i.technical_detail,
            }
            for i in report.issues
            if i.severity.value != "ok"  # Exclude passing checks from JSON
        ],
    }


def print_json(report: PrintabilityReport) -> None:
    """Print report as formatted JSON."""
    print(json.dumps(report_to_dict(report), indent=2))


def save_json(report: PrintabilityReport, path: str) -> None:
    """Save report to JSON file."""
    with open(path, 'w') as f:
        json.dump(report_to_dict(report), f, indent=2)
