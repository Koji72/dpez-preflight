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
python dpez.py model.stl --fast-repair             # Fast repair (skips pymeshfix)
python dpez.py model.stl --json                    # JSON output
python dpez.py models/*.stl                        # Batch processing
```

## Project Structure

```
dpez-preflight/
├── dpez.py                    # CLI entry point (Click-based)
├── core/
│   ├── models.py              # Severity, PrinterProfile, Issue, MeshStats, PrintabilityReport
│   ├── engine.py              # analyze_stl() orchestrator — runs analyzers, computes score
│   └── repair.py              # Auto-repair (winding, dedup, hole fill, debris/cavity removal)
├── analyzers/
│   ├── manifold.py            # Watertight/topology checks
│   ├── geometry.py            # Wall thickness, overhangs, floating geometry, interior cavities
│   └── scale.py               # Unit mismatch, build volume, aspect ratio
├── reporters/
│   ├── terminal.py            # Rich terminal output
│   └── json_reporter.py       # JSON output for API/pipeline
├── .claude/
│   ├── settings.json          # Claude Code project settings (hooks config)
│   ├── hooks/
│   │   └── session-start.sh   # Validates Python, deps, and core files on session start
│   └── skills/
│       ├── review-analyzer.md # Review an analyzer for correctness and conventions
│       ├── add-analyzer.md    # Create and wire a new analyzer module
│       ├── add-printer-profile.md # Add a new printer to the system
│       └── debug-score.md     # Investigate unexpected printability scores
├── requirements.txt
├── CLAUDE.md                  # ← You are here
└── README.md
```

## Code Conventions

- Python 3.9+ with type hints throughout
- Dataclasses for data structures, enums for constants
- Analyzers are standalone functions (not class methods) — composition over inheritance
- Each analyzer module returns a `list[Issue]`
- Try-catch with graceful degradation: individual analyzer failures don't crash the pipeline
- Reproducible randomness via `np.random.default_rng(seed=42)`
- Score penalties: CRITICAL = -25, WARNING = -10, INFO = -2

## Guardrails

### Do
- Wrap all trimesh/numpy calls in try-except inside analyzers
- Return empty `list[Issue]` on analyzer failure — never crash the pipeline
- Use `Issue.code` as a unique, uppercase, snake_case identifier (e.g., `"THIN_WALL"`)
- Keep analyzers stateless — no globals, no class instances
- Pre-compute shared data in `engine.py` and pass it to analyzers (e.g., `component_count`)
- Test changes with: `python dpez.py <test-file>.stl --json`

### Don't
- Don't add new dependencies without updating `requirements.txt`
- Don't modify `PrintabilityReport` fields without updating both reporters
- Don't use `mesh.split()` in multiple analyzers — it's expensive, compute once in engine
- Don't hardcode printer dimensions — always use `PrinterProfile` and the volumes dict
- Don't print to stdout from analyzers — all output goes through reporters

## Architecture Decisions

1. **Parallel analysis** — Analyzers run in a `ThreadPoolExecutor(max_workers=4)`. Wall thickness (ray-casting) is the bottleneck; other analyzers are fast.
2. **Single split pass** — `mesh.split()` is called once for repair, not per-analyzer. Component count is pre-computed via `connected_components()` in engine.
3. **Graceful optional deps** — `pymeshfix` and `pyvista` degrade gracefully if missing. Core analysis works without them.
4. **Score is subtractive** — Starts at 100, penalties subtracted per issue. Floor at 0.

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
