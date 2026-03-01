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


def repair_mesh(mesh: trimesh.Trimesh, fast: bool = False) -> Tuple[trimesh.Trimesh, list]:
    """
    Attempt automatic repair of common mesh issues.
    Returns (repaired_mesh, list_of_applied_fixes).

    When fast=True, skips pymeshfix hole filling (the slowest step on large meshes).
    Still performs winding fix, dedup, and debris/cavity removal.
    """
    applied_fixes = []

    # Step 1: Fix winding / normals (only if needed)
    if not mesh.is_winding_consistent:
        trimesh.repair.fix_winding(mesh)
        trimesh.repair.fix_normals(mesh)
        applied_fixes.append("Unified face winding order and fixed normals")

    # Step 2: Remove duplicate faces and vertices
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

    # Step 3: Fill holes using pymeshfix if available (only if mesh has holes)
    # Skipped in fast mode — pymeshfix is the bottleneck on large meshes (~990k+ faces)
    if fast and not mesh.is_watertight:
        applied_fixes.append("Hole fill skipped (fast mode)")
    elif not mesh.is_watertight and PYMESHFIX_AVAILABLE:
        try:
            mfix = pymeshfix.MeshFix(mesh.vertices, mesh.faces)
            # joincomp=False is much faster — skip joining disconnected shells
            mfix.repair(joincomp=False, remove_smallest_components=False)
            repaired = trimesh.Trimesh(
                vertices=mfix.points,
                faces=mfix.faces,
                process=False  # skip full reprocessing, we only need geometry
            )
            if repaired.is_watertight:
                mesh = repaired
                applied_fixes.append("Closed open holes using pymeshfix")
            else:
                mesh = repaired
                applied_fixes.append("Partial hole repair — some openings remain")
        except Exception as e:
            applied_fixes.append(f"Hole repair attempted but failed: {str(e)[:60]}")

    # Step 4: Remove floating debris and interior cavities (single split pass)
    try:
        components = trimesh.graph.connected_components(mesh.face_adjacency)
        component_count = len(list(components))

        if component_count > 1:
            bodies = mesh.split(only_watertight=False)

            # Sort by bounding box volume (largest = outer shell)
            body_info = []
            for b in bodies:
                try:
                    bb_vol = float(b.bounding_box.volume)
                    real_vol = abs(b.volume) if b.is_watertight else bb_vol * 0.1
                except Exception:
                    bb_vol, real_vol = 0.0, 0.0
                body_info.append({"body": b, "bb_vol": bb_vol, "vol": real_vol})
            body_info.sort(key=lambda x: x["bb_vol"], reverse=True)

            main_vol = body_info[0]["vol"]
            keep = [body_info[0]]
            debris_count = 0
            cavity_count = 0

            for info in body_info[1:]:
                # Remove tiny debris (<1% of main body)
                if info["vol"] < main_vol * 0.01:
                    debris_count += 1
                    continue

                # Check if this body is an interior cavity (enclosed inside a larger body)
                is_cavity = False
                centroid = info["body"].centroid.reshape(1, 3)
                for outer in keep:
                    if info["bb_vol"] > outer["bb_vol"] * 0.9:
                        continue
                    if not outer["body"].is_watertight:
                        continue
                    try:
                        if outer["body"].contains(centroid)[0]:
                            is_cavity = True
                            break
                    except Exception:
                        continue

                if is_cavity:
                    cavity_count += 1
                else:
                    keep.append(info)

            removed_total = debris_count + cavity_count
            if removed_total > 0 and keep:
                mesh = trimesh.util.concatenate([k["body"] for k in keep])
                if debris_count > 0:
                    applied_fixes.append(f"Removed {debris_count} floating geometry fragment(s)")
                if cavity_count > 0:
                    applied_fixes.append(f"Removed {cavity_count} interior cavity/ies (trapped shells)")
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
