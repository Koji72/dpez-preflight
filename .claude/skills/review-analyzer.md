# Skill: Review Analyzer Module

Review an analyzer module for correctness, performance, and adherence to project conventions.

## When to use
When modifying or creating an analyzer in `analyzers/`.

## Steps
1. Read the target analyzer file
2. Verify it returns `list[Issue]` — no side effects
3. Check that all `Issue` objects use valid `Severity` values and meaningful codes
4. Confirm try-catch wraps risky operations (trimesh calls, numpy ops) with graceful fallback
5. Look for unnecessary object copies or re-computation that could be cached
6. Verify reproducible randomness uses `np.random.default_rng(seed=42)` if sampling
7. Check that the function is standalone (no class, no global state)
8. Report findings with specific line numbers and suggested fixes
