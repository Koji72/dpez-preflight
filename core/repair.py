"""
dPEZ Preflight — Auto Repair Engine
Attempts to fix common mesh issues automatically.
"""
import trimesh
import numpy as np
from typing import Tuple
from core.models import PrintabilityReport, Issue, Severity

try:
    import pymeshfix
    PYMESHFIX_AVAILABLE = True
except ImportError:
    PYMESHFIX_AVAILABLE = False


def repair_mesh(mesh: trimesh.Trimesh) -> Tuple[trimesh.Trimesh, list]:
    """
    Attempt automatic repair of common mesh issues.
    Returns (repaired_mesh, list_of_applied_fixes).
    """
    applied_fixes = []
    
    # Step 1: Fix winding / normals
    if not mesh.is_winding_consistent:
        trimesh.repair.fix_winding(mesh)
        trimesh.repair.fix_normals(mesh)
        applied_fixes.append("Unified face winding order and fixed normals")

    # Step 2: Remove duplicate faces and vertices
    # trimesh >= 4.x: use merge_vertices() and filter degenerate faces
    verts_before = len(mesh.vertices)
    faces_before = len(mesh.faces)
    try:
        mesh.merge_vertices()
    except Exception:
        pass
    try:
        areas = mesh.area_faces
        valid = areas > 0
        if not valid.all():
            mesh.update_faces(valid)
    except Exception:
        pass
    verts_removed = verts_before - len(mesh.vertices)
    faces_removed = faces_before - len(mesh.faces)
    if verts_removed > 0 or faces_removed > 0:
        applied_fixes.append(
            f"Removed {verts_removed} duplicate vertex/vertices "
            f"and {faces_removed} degenerate triangle(s)"
        )

    # Step 3: Fill holes using pymeshfix if available
    if not mesh.is_watertight and PYMESHFIX_AVAILABLE:
        try:
            mfix = pymeshfix.MeshFix(mesh.vertices, mesh.faces)
            mfix.repair(joincomp=True, remove_smallest_components=True)
            repaired = trimesh.Trimesh(
                vertices=mfix.points,
                faces=mfix.faces,
                process=True
            )
            if repaired.is_watertight:
                mesh = repaired
                applied_fixes.append("Closed open holes using pymeshfix")
            else:
                mesh = repaired  # still use cleaned version even if not fully watertight
                applied_fixes.append("Partial hole repair — some openings remain")
        except Exception as e:
            applied_fixes.append(f"Hole repair attempted but failed: {str(e)[:60]}")

    # Step 4: Remove small floating bodies
    try:
        bodies = mesh.split(only_watertight=False)
        if len(bodies) > 1:
            volumes = []
            for b in bodies:
                try:
                    v = abs(b.volume) if b.is_watertight else b.bounding_box.volume * 0.1
                    volumes.append((v, b))
                except Exception:
                    volumes.append((0, b))
            
            main_vol = max(v for v, _ in volumes)
            significant = [b for v, b in volumes if v >= main_vol * 0.01]
            removed = len(volumes) - len(significant)
            
            if removed > 0 and significant:
                mesh = trimesh.util.concatenate(significant)
                applied_fixes.append(f"Removed {removed} floating geometry fragment(s)")
    except Exception:
        pass

    return mesh, applied_fixes


def export_repaired(mesh: trimesh.Trimesh, output_path: str) -> bool:
    """Export repaired mesh to STL."""
    try:
        mesh.export(output_path)
        return True
    except Exception:
        return False
