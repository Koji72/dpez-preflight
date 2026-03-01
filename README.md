# dPEZ Preflight v0.1.0
**STL printability analyzer for FDM — stop wasting filament.**

---

## Install

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
# Analyze a single file (default: Bambu X1C)
python dpez.py my_model.stl

# Specify printer
python dpez.py my_model.stl --printer prusa-mk4

# Auto-repair and export fixed STL
python dpez.py broken.stl --repair --output fixed.stl

# JSON output (for pipelines / API)
python dpez.py my_model.stl --json

# Batch analyze entire folder
python dpez.py models/*.stl --printer bambu-p1s
```

---

## Supported Printers

| Flag           | Printer               |
|----------------|-----------------------|
| `bambu-x1c`    | Bambu X1C / X1E       |
| `bambu-p1s`    | Bambu P1S             |
| `bambu-p1p`    | Bambu P1P             |
| `prusa-mk4`    | Prusa MK4             |
| `prusa-mini`   | Prusa MINI+           |
| `generic`      | Generic FDM           |

---

## What It Detects

| Code                      | Severity | Description                                       |
|---------------------------|----------|---------------------------------------------------|
| `OPEN_MESH`               | CRITICAL | Non-watertight mesh (holes)                       |
| `INCONSISTENT_WINDING`    | CRITICAL | Inverted normals                                  |
| `THIN_WALLS`              | CRITICAL | Walls below printer's minimum nozzle width        |
| `SUSPICIOUS_SCALE_TINY`   | CRITICAL | Possible unit mismatch (inches/meters vs mm)      |
| `EXCEEDS_BUILD_VOLUME`    | WARNING  | Model larger than printer build plate             |
| `MULTIPLE_BODIES`         | WARNING  | Disconnected geometry bodies                      |
| `HEAVY_OVERHANGS`         | WARNING  | >15% of faces exceed 45° without support         |
| `FLOATING_GEOMETRY`       | WARNING  | Stray vertices / sculpting artifacts              |
| `SUSPICIOUS_SCALE_GIANT`  | WARNING  | Possible incorrect scale                          |
| `EXTREME_ASPECT_RATIO`    | INFO     | Warping/adhesion risk for thin tall models        |
| `MODERATE_OVERHANGS`      | INFO     | Some overhangs, consider orientation              |

---

## Score System

| Score   | Verdict                     |
|---------|-----------------------------|
| 80–100  | ✅ Ready to print            |
| 50–79   | ⚠️  Printable with warnings  |
| 0–49    | ❌ Not ready                 |

---

## Project Structure

```
dpez_preflight/
├── dpez.py                   ← CLI entry point
├── requirements.txt
├── core/
│   ├── models.py             ← Data structures
│   ├── engine.py             ← Analysis orchestrator
│   └── repair.py             ← Auto-repair engine
├── analyzers/
│   ├── manifold.py           ← Watertight / normals checks
│   ├── geometry.py           ← Walls, overhangs, floating geo
│   └── scale.py              ← Dimensions, units, build volume
├── reporters/
│   ├── terminal.py           ← Rich CLI output
│   └── json_reporter.py      ← JSON output for API/pipeline
└── samples/                  ← Test STL files
```

---

## Roadmap

- [ ] v0.2 — Pattern database (error types by model category)
- [ ] v0.3 — Filament profiles (PLA / PETG / ABS behavior)
- [ ] v0.4 — Web API (FastAPI wrapper)
- [ ] v0.5 — MakerWorld integration + dPEZ Verified badge
- [ ] v1.0 — Bambu Studio plugin
