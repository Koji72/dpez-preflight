"""
dPEZ Preflight — Scale & Dimensions Analyzer
Detects incorrect scale, units confusion, and build volume violations.
"""
import trimesh
import numpy as np
from typing import List, Tuple
from core.models import Issue, Severity, PrinterProfile


# Build volumes in mm (X, Y, Z)
PRINTER_BUILD_VOLUME: dict = {
    PrinterProfile.BAMBU_X1C:   (256, 256, 256),
    PrinterProfile.BAMBU_P1S:   (256, 256, 256),
    PrinterProfile.BAMBU_P1P:   (256, 256, 256),
    PrinterProfile.PRUSA_MK4:   (250, 210, 220),
    PrinterProfile.PRUSA_MINI:  (180, 180, 180),
    PrinterProfile.GENERIC_FDM: (200, 200, 200),
}

# Models this small are likely exported in wrong units (inches → mm confusion)
SUSPICIOUS_TINY_MM  = 5.0     # < 5mm total → probably exported in wrong units
SUSPICIOUS_GIANT_MM = 2000.0  # > 2000mm → clearly wrong scale


def analyze_scale(mesh: trimesh.Trimesh, printer: PrinterProfile) -> List[Issue]:
    issues = []
    
    bounds = mesh.bounding_box.extents  # (x, y, z) dimensions
    max_dim = float(np.max(bounds))
    min_dim = float(np.min(bounds))
    build = PRINTER_BUILD_VOLUME.get(printer, (200, 200, 200))
    
    # --- Units confusion detection ---
    if max_dim < SUSPICIOUS_TINY_MM:
        # Probably exported in meters or inches when slicer expects mm
        scale_factor = 25.4 if max_dim < 1.0 else 1000.0
        unit_guess = "meters" if max_dim < 0.1 else "inches"
        issues.append(Issue(
            code="SUSPICIOUS_SCALE_TINY",
            severity=Severity.CRITICAL,
            title=f"Model appears too small — possible unit mismatch",
            description=(
                f"Largest dimension is {max_dim:.3f}mm. This is smaller than a grain of rice. "
                f"STL files are unitless but slicers assume millimeters. "
                f"If your source app exports in {unit_guess}, multiply by {scale_factor:.0f}x."
            ),
            auto_fixable=True,
            fix_description=f"Scale ×{scale_factor:.0f} to convert from {unit_guess} to mm.",
            technical_detail=f"extents={bounds.tolist()}"
        ))

    elif max_dim > SUSPICIOUS_GIANT_MM:
        issues.append(Issue(
            code="SUSPICIOUS_SCALE_GIANT",
            severity=Severity.WARNING,
            title=f"Model is extremely large ({max_dim:.0f}mm)",
            description=(
                f"Largest dimension is {max_dim:.0f}mm ({max_dim/1000:.2f}m). "
                f"Verify this is intentional. If exported in mm from a scene in cm, "
                f"scale by ×0.1."
            ),
            auto_fixable=False,
            technical_detail=f"extents={bounds.tolist()}"
        ))

    # --- Build volume check ---
    exceeds = []
    axes = ['X', 'Y', 'Z']
    for i, (model_dim, build_dim, axis) in enumerate(zip(bounds, build, axes)):
        if model_dim > build_dim:
            exceeds.append(f"{axis}: {model_dim:.1f}mm > {build_dim}mm")
    
    if exceeds:
        issues.append(Issue(
            code="EXCEEDS_BUILD_VOLUME",
            severity=Severity.WARNING,
            title=f"Model exceeds {printer.value} build volume",
            description=(
                f"Model dimensions ({bounds[0]:.1f} × {bounds[1]:.1f} × {bounds[2]:.1f}mm) "
                f"exceed printer limits ({build[0]} × {build[1]} × {build[2]}mm). "
                f"Oversize axes: {', '.join(exceeds)}. "
                f"You'll need to scale down or split the model."
            ),
            auto_fixable=False,
            fix_description="Scale down in slicer or split model into printable sections.",
            technical_detail=f"model={bounds.tolist()}, build={list(build)}"
        ))
    else:
        fit_pct = max(b/bv*100 for b, bv in zip(bounds, build))
        issues.append(Issue(
            code="SCALE_OK",
            severity=Severity.OK,
            title=f"Dimensions fit {printer.value} build volume",
            description=(
                f"Model: {bounds[0]:.1f} × {bounds[1]:.1f} × {bounds[2]:.1f}mm — "
                f"uses {fit_pct:.0f}% of largest build axis."
            ),
        ))

    # --- Extreme aspect ratio warning ---
    if min_dim > 0:
        aspect_ratio = max_dim / min_dim
        if aspect_ratio > 20:
            issues.append(Issue(
                code="EXTREME_ASPECT_RATIO",
                severity=Severity.INFO,
                title=f"Extreme aspect ratio ({aspect_ratio:.0f}:1)",
                description=(
                    f"One dimension is {aspect_ratio:.0f}× another. "
                    f"Very thin/tall models are prone to warping and adhesion failure. "
                    f"Consider adding a brim in slicer settings."
                ),
                auto_fixable=False,
                fix_description="Add brim in slicer, or split model to reduce warping risk.",
            ))

    return issues
