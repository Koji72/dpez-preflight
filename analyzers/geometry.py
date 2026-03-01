"""
dPEZ Preflight — Wall Thickness & Print Geometry Analyzer
Detects walls too thin to print, floating geometry, and extreme overhangs.
"""
import trimesh
import numpy as np
from typing import List, Dict
from core.models import Issue, Severity, PrinterProfile


# Minimum wall thickness by printer (in mm)
PRINTER_MIN_WALL: Dict[PrinterProfile, float] = {
    PrinterProfile.BAMBU_X1C:   0.4,
    PrinterProfile.BAMBU_P1S:   0.4,
    PrinterProfile.BAMBU_P1P:   0.4,
    PrinterProfile.PRUSA_MK4:   0.4,
    PrinterProfile.PRUSA_MINI:  0.4,
    PrinterProfile.GENERIC_FDM: 0.8,   # Conservative for unknowns
}

# Maximum overhang angle before supports required (degrees from horizontal)
MAX_OVERHANG_ANGLE = 45.0


def analyze_wall_thickness(mesh: trimesh.Trimesh, printer: PrinterProfile) -> List[Issue]:
    """
    Estimate minimum wall thickness using ray casting approach.
    Flags walls thinner than the printer's nozzle diameter.
    """
    issues = []
    min_wall = PRINTER_MIN_WALL.get(printer, 0.8)

    try:
        # Sample face centroids and cast rays inward along face normals
        # to estimate local thickness. Seed for reproducibility.
        rng = np.random.default_rng(seed=42)
        sample_count = min(500, len(mesh.faces))
        sample_indices = rng.choice(len(mesh.faces), sample_count, replace=False)
        
        face_centers = mesh.triangles_center[sample_indices]
        face_normals = mesh.face_normals[sample_indices]
        
        # Cast rays inward (opposite normal direction)
        ray_origins = face_centers + face_normals * 0.01  # small offset
        ray_directions = -face_normals
        
        locations, index_ray, _ = mesh.ray.intersects_location(
            ray_origins=ray_origins,
            ray_directions=ray_directions,
            multiple_hits=False
        )
        
        if len(locations) > 0:
            # Thickness = distance from origin to hit point
            hit_origins = ray_origins[index_ray]
            distances = np.linalg.norm(locations - hit_origins, axis=1)
            
            thin_walls = distances[distances < min_wall]
            thin_ratio = len(thin_walls) / max(len(distances), 1)
            
            if len(thin_walls) > 0 and thin_ratio > 0.02:  # >2% of sampled faces
                min_detected = float(np.min(thin_walls))
                issues.append(Issue(
                    code="THIN_WALLS",
                    severity=Severity.CRITICAL if min_detected < min_wall * 0.5 else Severity.WARNING,
                    title=f"Walls thinner than {min_wall}mm detected",
                    description=(
                        f"~{int(thin_ratio * 100)}% of sampled surfaces have wall thickness "
                        f"below {min_wall}mm (minimum for {printer.value}). "
                        f"Thinnest detected: {min_detected:.2f}mm. "
                        f"These sections will print as air or collapse mid-print."
                    ),
                    affected_count=len(thin_walls),
                    auto_fixable=False,
                    fix_description=f"Thicken walls to minimum {min_wall}mm in ZBrush (ZRemesher + Polish) or source app.",
                    technical_detail=f"min_thickness={min_detected:.3f}mm, threshold={min_wall}mm"
                ))
            else:
                issues.append(Issue(
                    code="WALL_THICKNESS_OK",
                    severity=Severity.OK,
                    title=f"Wall thickness looks adequate for {printer.value}",
                    description=f"No walls below {min_wall}mm threshold detected in sample.",
                ))
    except Exception as e:
        issues.append(Issue(
            code="WALL_ANALYSIS_SKIPPED",
            severity=Severity.INFO,
            title="Wall thickness analysis skipped",
            description=f"Could not complete ray-cast analysis: {str(e)[:80]}",
        ))

    return issues


def analyze_overhangs(mesh: trimesh.Trimesh) -> List[Issue]:
    """
    Detect faces that overhang beyond 45 degrees without support.
    Faces pointing downward = problem zones.
    """
    issues = []

    try:
        face_normals = mesh.face_normals
        
        # Z component of normal: -1 = fully downward, 0 = vertical, 1 = upward
        z_components = face_normals[:, 2]
        
        # A face is an overhang if its normal points downward past 45°
        # cos(135°) = -0.707 → normal Z < -0.707
        overhang_threshold = -np.cos(np.radians(MAX_OVERHANG_ANGLE))  # -0.707
        
        overhang_faces = np.where(z_components < overhang_threshold)[0]
        overhang_ratio = len(overhang_faces) / max(len(face_normals), 1)
        
        if overhang_ratio > 0.15:  # >15% of faces are extreme overhangs
            issues.append(Issue(
                code="HEAVY_OVERHANGS",
                severity=Severity.WARNING,
                title=f"Heavy overhangs detected ({int(overhang_ratio*100)}% of faces)",
                description=(
                    f"{len(overhang_faces):,} faces exceed 45° overhang angle. "
                    f"This model will require significant support structures. "
                    f"Consider reorienting the model or redesigning bridging sections "
                    f"to reduce support material and improve surface quality."
                ),
                affected_count=len(overhang_faces),
                auto_fixable=False,
                fix_description="Re-orient model in slicer or use manual supports at critical zones.",
                technical_detail=f"overhang_faces={len(overhang_faces)}, ratio={overhang_ratio:.2%}"
            ))
        elif overhang_ratio > 0.05:
            issues.append(Issue(
                code="MODERATE_OVERHANGS",
                severity=Severity.INFO,
                title=f"Moderate overhangs present ({int(overhang_ratio*100)}% of faces)",
                description=(
                    f"Some overhangs exceed 45°. Consider orientation in slicer "
                    f"to minimize support usage."
                ),
                affected_count=len(overhang_faces),
                auto_fixable=False,
                technical_detail=f"overhang_faces={len(overhang_faces)}, ratio={overhang_ratio:.2%}"
            ))
        else:
            issues.append(Issue(
                code="OVERHANGS_OK",
                severity=Severity.OK,
                title="Overhang profile is print-friendly",
                description=f"Less than 5% of faces exceed 45° overhang threshold.",
            ))

    except Exception as e:
        issues.append(Issue(
            code="OVERHANG_ANALYSIS_SKIPPED",
            severity=Severity.INFO,
            title="Overhang analysis skipped",
            description=str(e)[:100],
        ))

    return issues


def analyze_floating_geometry(mesh: trimesh.Trimesh) -> List[Issue]:
    """
    Detect geometry that has no connection to the main body.
    Floating pieces = print artifacts or failures.
    """
    issues = []
    
    try:
        # Split into bodies and check for small disconnected pieces
        bodies = mesh.split(only_watertight=False)
        
        if len(bodies) > 1:
            # Sort by volume
            volumes = []
            for b in bodies:
                try:
                    v = abs(b.volume) if b.is_watertight else b.bounding_box.volume * 0.1
                    volumes.append(v)
                except Exception:
                    volumes.append(0)
            
            total_vol = sum(volumes)
            main_vol = max(volumes) if volumes else 0
            
            # Flag bodies that are <1% of main body volume (likely debris/artifacts)
            debris = [v for v in volumes if v < main_vol * 0.01]
            
            if debris:
                issues.append(Issue(
                    code="FLOATING_GEOMETRY",
                    severity=Severity.WARNING,
                    title=f"{len(debris)} floating geometry piece(s) detected",
                    description=(
                        f"Found {len(debris)} disconnected geometry fragment(s) "
                        f"much smaller than the main body. These are likely sculpting "
                        f"artifacts or stray vertices that will print as blobs or "
                        f"be ignored by the slicer unpredictably."
                    ),
                    affected_count=len(debris),
                    auto_fixable=True,
                    fix_description="Auto-repair can remove bodies smaller than 1% of total volume.",
                    technical_detail=f"total_bodies={len(bodies)}, debris_count={len(debris)}"
                ))
    except Exception:
        pass

    return issues
