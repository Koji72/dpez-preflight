"""
dPEZ Preflight — Auto Repair Engine
Attempts to fix common mesh issues automatically.

Pipeline (optimized order):
  1. Fix winding / normals
  2. Remove degenerate faces and merge duplicate vertices
  3. Split → remove debris & interior cavities (cheap, removes ~99% of components)
  4. Per-component hole fill in parallel (pymeshfix only touches the few remaining bodies)
  5. Recombine

Key insight: debris removal BEFORE hole fill means pymeshfix never sees the
full 990k-face mesh — it processes a handful of small components in parallel.
"""
import trimesh
import numpy as np
from typing import Tuple, List
from concurrent.futures import ProcessPoolExecutor, as_completed
from core.models import PrintabilityReport, Issue, Severity

try:
    import pymeshfix
    PYMESHFIX_AVAILABLE = True
except ImportError:
    PYMESHFIX_AVAILABLE = False


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _classify_bodies(mesh: trimesh.Trimesh) -> Tuple[list, int, int]:
    """
    Split mesh into components; classify each as keep / debris / cavity.
    Returns (kept_bodies, debris_count, cavity_count).
    """
    try:
        components = trimesh.graph.connected_components(mesh.face_adjacency)
        if len(list(components)) <= 1:
            return [mesh], 0, 0
    except Exception:
        return [mesh], 0, 0

    bodies = mesh.split(only_watertight=False)
    if len(bodies) <= 1:
        return [mesh], 0, 0

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
        # Tiny debris (<1% of main body)
        if info["vol"] < main_vol * 0.01:
            debris_count += 1
            continue

        # Interior cavity check
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

    return [k["body"] for k in keep], debris_count, cavity_count


def _fix_component_holes(verts_faces: Tuple[np.ndarray, np.ndarray]) -> Tuple[np.ndarray, np.ndarray, bool]:
    """
    Repair a single component with pymeshfix (runs in a subprocess).
    Accepts (vertices, faces) and returns (vertices, faces, success).
    Designed for ProcessPoolExecutor — must be picklable and import-free at module level.
    """
    verts, faces = verts_faces
    try:
        import pymeshfix as _pmf
        mfix = _pmf.MeshFix(verts, faces)
        mfix.repair(joincomp=False, remove_smallest_components=False)
        return mfix.points, mfix.faces, True
    except Exception:
        return verts, faces, False


# ---------------------------------------------------------------------------
#  Main repair entry point
# ---------------------------------------------------------------------------

def repair_mesh(mesh: trimesh.Trimesh, fast: bool = False) -> Tuple[trimesh.Trimesh, list]:
    """
    Attempt automatic repair of common mesh issues.
    Returns (repaired_mesh, list_of_applied_fixes).

    Pipeline:
      1. Fix winding / normals
      2. Remove degenerate faces and merge duplicate vertices
      3. Remove debris & interior cavities FIRST (cheap — kills ~99% of components)
      4. Fill holes per-component in parallel (pymeshfix only on surviving bodies)

    When fast=True, uses trimesh fill_holes instead of pymeshfix in step 4.
    """
    applied_fixes = []

    # ── Step 1: Fix winding / normals ──
    if not mesh.is_winding_consistent:
        trimesh.repair.fix_winding(mesh)
        trimesh.repair.fix_normals(mesh)
        applied_fixes.append("Unified face winding order and fixed normals")

    # ── Step 2: Remove degenerate faces and merge duplicate vertices ──
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

    # ── Step 3: Remove debris & cavities BEFORE hole fill ──
    # This is the key optimisation: on father.stl this drops 2,843 debris
    # fragments, leaving ~14 bodies instead of 2,597 for pymeshfix to process.
    kept_bodies, debris_count, cavity_count = _classify_bodies(mesh)

    if debris_count > 0:
        applied_fixes.append(f"Removed {debris_count} floating geometry fragment(s)")
    if cavity_count > 0:
        applied_fixes.append(f"Removed {cavity_count} interior cavity/ies (trapped shells)")

    # Recombine kept bodies (or keep single mesh)
    if len(kept_bodies) == 1:
        mesh = kept_bodies[0]
    elif kept_bodies:
        mesh = trimesh.util.concatenate(kept_bodies)

    # ── Step 4: Fill holes — per-component, in parallel ──
    if mesh.is_watertight:
        # Nothing to repair
        pass
    elif fast:
        # Fast mode: lightweight trimesh fill_holes
        try:
            trimesh.repair.fill_holes(mesh)
            if mesh.is_watertight:
                applied_fixes.append("Closed open holes using trimesh fill_holes (fast mode)")
            else:
                applied_fixes.append(
                    "Partial hole repair via trimesh fill_holes (fast mode) — some openings remain"
                )
        except Exception:
            applied_fixes.append("Hole fill skipped (fast mode — trimesh fill_holes failed)")
    elif PYMESHFIX_AVAILABLE:
        # Full mode: pymeshfix per-component in parallel
        # Split into components so each pymeshfix call is small and fast
        try:
            components = mesh.split(only_watertight=False)
        except Exception:
            components = [mesh]

        # Separate watertight (no repair needed) from open components
        watertight_bodies = []
        open_bodies = []
        for comp in components:
            if comp.is_watertight:
                watertight_bodies.append(comp)
            else:
                open_bodies.append(comp)

        if open_bodies:
            repaired_bodies = []
            repair_ok = 0
            repair_partial = 0

            # Parallel pymeshfix across open components
            tasks = [(comp.vertices.copy(), comp.faces.copy()) for comp in open_bodies]
            max_workers = min(4, len(tasks))

            try:
                with ProcessPoolExecutor(max_workers=max_workers) as pool:
                    futures = {pool.submit(_fix_component_holes, t): i for i, t in enumerate(tasks)}
                    for future in as_completed(futures):
                        try:
                            rv, rf, ok = future.result(timeout=60)
                            repaired = trimesh.Trimesh(vertices=rv, faces=rf, process=False)
                            repaired_bodies.append(repaired)
                            if ok and repaired.is_watertight:
                                repair_ok += 1
                            else:
                                repair_partial += 1
                        except Exception:
                            # Keep original on failure
                            idx = futures[future]
                            repaired_bodies.append(open_bodies[idx])
                            repair_partial += 1
            except Exception:
                # ProcessPool failed entirely — fall back to sequential
                for comp in open_bodies:
                    try:
                        mfix = pymeshfix.MeshFix(comp.vertices, comp.faces)
                        mfix.repair(joincomp=False, remove_smallest_components=False)
                        fixed = trimesh.Trimesh(vertices=mfix.points, faces=mfix.faces, process=False)
                        repaired_bodies.append(fixed)
                        if fixed.is_watertight:
                            repair_ok += 1
                        else:
                            repair_partial += 1
                    except Exception:
                        repaired_bodies.append(comp)
                        repair_partial += 1

            all_bodies = watertight_bodies + repaired_bodies
            if all_bodies:
                mesh = trimesh.util.concatenate(all_bodies) if len(all_bodies) > 1 else all_bodies[0]

            total_open = len(open_bodies)
            if repair_ok == total_open:
                applied_fixes.append(
                    f"Closed holes in {repair_ok} component(s) using pymeshfix (parallel)"
                )
            elif repair_ok > 0:
                applied_fixes.append(
                    f"Repaired {repair_ok}/{total_open} open component(s) via pymeshfix (parallel); "
                    f"{repair_partial} partially repaired"
                )
            else:
                applied_fixes.append(
                    f"Partial hole repair on {total_open} component(s) — some openings remain"
                )

    return mesh, applied_fixes


def export_repaired(mesh: trimesh.Trimesh, output_path: str) -> bool:
    """Export repaired mesh to STL."""
    try:
        mesh.export(output_path)
        return True
    except Exception:
        return False
