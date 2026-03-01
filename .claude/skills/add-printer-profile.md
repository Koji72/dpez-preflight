# Skill: Add Printer Profile

Add a new FDM printer profile to the system.

## When to use
When supporting a new 3D printer model.

## Steps
1. Add new entry to `PrinterProfile` enum in `core/models.py`
2. Add build volume and printer specs to `analyzers/scale.py` → `PRINTER_VOLUMES` dict
3. Add CLI mapping in `dpez.py` → `PRINTER_MAP` dict
4. Verify the new profile works with all analyzers (scale, geometry, manifold)
5. Update `CLAUDE.md` project overview with the new printer count
6. Test with: `python dpez.py test.stl --printer <new-profile-id>`
