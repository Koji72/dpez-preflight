# CLAUDE.md

## Project Overview

dPEZ Preflight is a Python CLI tool that analyzes STL files for 3D printing issues before printing. It detects mesh integrity problems, geometry issues, and scale errors across 6 FDM printer profiles (Bambu X1C/X1E/P1S/P1P, Prusa MK4/MINI+, Generic). Version 0.1.0.

## Setup

```bash
pip install -r requirements.txt
```

## Running the Tool

```bash
python dpez.py model.stl                          # Analyze a file
python dpez.py model.stl --printer prusa-mk4       # Specific printer
python dpez.py model.stl --repair --output fixed.stl  # Auto-repair
python dpez.py model.stl --json                    # JSON output
python dpez.py models/*.stl                        # Batch processing
```

## Project Structure

- `dpez.py` — CLI entry point (Click-based), defines version
- `core/models.py` — Data structures: `Severity` enum, `PrinterProfile` enum, `Issue`/`MeshStats`/`PrintabilityReport` dataclasses
- `core/engine.py` — Main `analyze_stl()` orchestrator that runs all analyzers and computes score
- `core/repair.py` — Auto-repair engine (winding fix, dedup, hole fill via pymeshfix, debris removal)
- `analyzers/manifold.py` — Watertight/topology checks (open mesh, winding, multiple bodies)
- `analyzers/geometry.py` — Wall thickness (ray-cast sampling), overhang detection, floating geometry
- `analyzers/scale.py` — Unit mismatch, build volume validation, aspect ratio checks
- `reporters/terminal.py` — Rich terminal output with colored tables and panels
- `reporters/json_reporter.py` — JSON output for API/pipeline integration

## Code Conventions

- Python 3 with type hints throughout
- Dataclasses for data structures, enums for constants
- Analyzers are standalone functions (not class methods) — composition over inheritance
- Each analyzer module returns a `list[Issue]`
- Try-catch with graceful degradation: individual analyzer failures don't crash the pipeline
- Reproducible randomness via `np.random.default_rng(seed=42)`
- Score penalties: CRITICAL = -25, WARNING = -10, INFO = -2

## Key Dependencies

- **trimesh** — Mesh loading and geometry analysis
- **numpy** — Numerical operations
- **click** — CLI framework
- **rich** — Terminal formatting
- **pymeshfix** — Mesh hole repair (optional graceful fallback)
- **pyvista** — 3D visualization support

## Testing

No test suite exists yet. Testing is manual via CLI invocation.

## Linting

No linter configuration exists yet.
