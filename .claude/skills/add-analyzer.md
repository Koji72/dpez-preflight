# Skill: Add New Analyzer

Create a new analysis module and wire it into the pipeline.

## When to use
When adding a new type of mesh check (e.g., thin features, bridging, support detection).

## Conventions
- Analyzer must be a standalone function, not a class method
- Must return `list[Issue]`
- Must handle its own exceptions (never crash the pipeline)
- Must accept `mesh: trimesh.Trimesh` as first argument

## Steps
1. Create new file in `analyzers/` (e.g., `analyzers/bridges.py`)
2. Implement analyzer function with signature: `def analyze_bridges(mesh, ...) -> list[Issue]`
3. Wrap all trimesh/numpy calls in try-except, return empty list on failure
4. Import and add to `core/engine.py` → `analyze_stl()` thread pool
5. Add new analyzer to the project structure section of `CLAUDE.md`
6. Test: `python dpez.py test.stl` — verify no crashes and issues appear
