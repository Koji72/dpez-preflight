# Skill: Debug Printability Score

Investigate why a file gets an unexpected score.

## When to use
When a user reports a score that seems too high or too low.

## Steps
1. Run: `python dpez.py <file> --json` to get the full report
2. List all issues by severity and their penalty values:
   - CRITICAL = -25 points
   - WARNING = -10 points
   - INFO = -2 points
3. Calculate expected score: `100 - sum(penalties)`
4. Compare with reported score
5. If mismatch, check `core/engine.py` → score calculation loop
6. Check if any analyzer is silently failing (swallowed exceptions returning no issues)
7. Check if duplicate issues inflate the penalty
