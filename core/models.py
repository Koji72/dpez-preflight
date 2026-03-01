"""
dPEZ Preflight — Core Data Models
Structured results that flow through the entire analysis pipeline.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple
import numpy as np


class Severity(Enum):
    CRITICAL = "critical"   # Will definitely fail to print
    WARNING  = "warning"    # May cause problems
    INFO     = "info"       # Optimization suggestions
    OK       = "ok"         # Passed check


class PrinterProfile(Enum):
    BAMBU_X1C   = "Bambu X1C / X1E"
    BAMBU_P1S   = "Bambu P1S"
    BAMBU_P1P   = "Bambu P1P"
    PRUSA_MK4   = "Prusa MK4"
    PRUSA_MINI  = "Prusa MINI+"
    GENERIC_FDM = "Generic FDM"


@dataclass
class Issue:
    """A single detected problem in the mesh."""
    code: str               # e.g. "NON_MANIFOLD_EDGES"
    severity: Severity
    title: str
    description: str
    location: Optional[str] = None          # Human readable location hint
    affected_count: int = 0                 # How many vertices/faces affected
    auto_fixable: bool = False
    fix_description: Optional[str] = None
    technical_detail: Optional[str] = None


@dataclass
class MeshStats:
    """Raw geometric statistics of the mesh."""
    vertex_count: int = 0
    face_count: int = 0
    edge_count: int = 0
    surface_area: float = 0.0       # mm²
    volume: float = 0.0             # mm³
    bounding_box: Optional[Tuple] = None    # (x, y, z) dimensions in mm
    is_watertight: bool = False
    is_winding_consistent: bool = False
    component_count: int = 0        # Separate bodies in mesh


@dataclass
class PrintabilityReport:
    """Full analysis result for a single STL file."""
    filename: str
    file_size_kb: float
    printer: PrinterProfile
    
    mesh_stats: MeshStats = field(default_factory=MeshStats)
    issues: List[Issue] = field(default_factory=list)
    
    # Scores
    score: int = 100                    # 0–100, starts perfect
    ready_to_print: bool = False
    verdict: str = ""
    
    # Timing
    analysis_time_ms: float = 0.0
    
    def critical_issues(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == Severity.CRITICAL]
    
    def warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]
    
    def infos(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == Severity.INFO]
    
    def auto_fixable_issues(self) -> List[Issue]:
        return [i for i in self.issues if i.auto_fixable]
