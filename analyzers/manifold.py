"""
dPEZ Preflight — Manifold & Topology Analyzer
Detects holes, non-manifold edges, and mesh integrity issues.
"""
import trimesh
import numpy as np
from typing import List
from core.models import Issue, Severity


def analyze_manifold(mesh: trimesh.Trimesh, component_count: int = None) -> List[Issue]:
    """
    Check if mesh is watertight (manifold).
    A non-watertight mesh = open holes = print failure guaranteed.
    Accepts precomputed component_count to avoid redundant graph traversal.
    """
    issues = []

    # --- Watertight check ---
    if not mesh.is_watertight:
        # Use trimesh's built-in boundary detection
        try:
            boundary_edges = trimesh.graph.boundary_loops(mesh)
            hole_count = len(boundary_edges)
        except Exception:
            hole_count = "unknown number of"

        issues.append(Issue(
            code="OPEN_MESH",
            severity=Severity.CRITICAL,
            title="Mesh is not watertight (has holes)",
            description=(
                f"The model has {hole_count} open boundary loop(s). "
                f"FDM slicers cannot calculate a valid volume, which causes "
                f"incorrect infill, missing walls, or complete slice failure."
            ),
            affected_count=hole_count if isinstance(hole_count, int) else 0,
            auto_fixable=True,
            fix_description="Auto-repair can close most simple holes using pymeshfix.",
            technical_detail="mesh.is_watertight = False"
        ))

    # --- Multiple bodies check (use precomputed count) ---
    try:
        if component_count is None:
            components = trimesh.graph.connected_components(mesh.face_adjacency)
            component_count = len(list(components))

        if component_count > 1:
            issues.append(Issue(
                code="MULTIPLE_BODIES",
                severity=Severity.WARNING,
                title=f"Mesh has {component_count} disconnected bodies",
                description=(
                    f"The file contains {component_count} separate geometric bodies. "
                    f"This is common in assemblies or decorative models, but can cause "
                    f"unexpected infill behavior. Each body should be intentional."
                ),
                affected_count=component_count,
                auto_fixable=False,
                fix_description="Review in ZBrush/Blender — merge if bodies should be connected.",
                technical_detail=f"connected_components = {component_count}"
            ))
    except Exception:
        pass

    # --- Winding consistency ---
    if not mesh.is_winding_consistent:
        issues.append(Issue(
            code="INCONSISTENT_WINDING",
            severity=Severity.CRITICAL,
            title="Face winding order is inconsistent (inverted normals)",
            description=(
                "Some faces have their normals pointing inward instead of outward. "
                "This causes slicers to misidentify inside/outside surfaces, "
                "resulting in missing walls or inverted geometry."
            ),
            affected_count=0,
            auto_fixable=True,
            fix_description="Auto-repair can unify winding order using trimesh.fix_normals().",
            technical_detail="mesh.is_winding_consistent = False"
        ))

    if mesh.is_watertight and mesh.is_winding_consistent:
        issues.append(Issue(
            code="MANIFOLD_OK",
            severity=Severity.OK,
            title="Mesh topology is clean",
            description="Watertight, consistent winding. No manifold errors detected.",
        ))

    return issues
