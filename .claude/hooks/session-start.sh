#!/usr/bin/env bash
# dPEZ Preflight — Session Start Hook
# Validates the development environment on every Claude Code session start.
# Ensures dependencies are installed and the project is in a runnable state.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ERRORS=()

echo "🔧 dPEZ Preflight — Environment Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Python version check (3.9+)
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
        ERRORS+=("Python 3.9+ required, found $PY_VERSION")
    else
        echo "✓ Python $PY_VERSION"
    fi
else
    ERRORS+=("Python 3 not found in PATH")
fi

# 2. Check core dependencies
DEPS=("trimesh" "numpy" "click" "rich")
for dep in "${DEPS[@]}"; do
    if python3 -c "import $dep" 2>/dev/null; then
        echo "✓ $dep installed"
    else
        ERRORS+=("Missing dependency: $dep — run 'pip install -r requirements.txt'")
    fi
done

# 3. Check optional dependencies (warn, don't fail)
OPTIONAL=("pymeshfix" "pyvista")
for dep in "${OPTIONAL[@]}"; do
    if python3 -c "import $dep" 2>/dev/null; then
        echo "✓ $dep installed (optional)"
    else
        echo "⚠ $dep not installed (optional — repair/visualization may be limited)"
    fi
done

# 4. Check that core project files exist
CORE_FILES=("dpez.py" "core/engine.py" "core/models.py" "core/repair.py" "analyzers/manifold.py" "analyzers/geometry.py" "analyzers/scale.py")
for f in "${CORE_FILES[@]}"; do
    if [ ! -f "$PROJECT_ROOT/$f" ]; then
        ERRORS+=("Missing core file: $f")
    fi
done
echo "✓ Core project files present"

# 5. Git status summary
if command -v git &>/dev/null && [ -d "$PROJECT_ROOT/.git" ]; then
    BRANCH=$(git -C "$PROJECT_ROOT" branch --show-current 2>/dev/null || echo "unknown")
    DIRTY=$(git -C "$PROJECT_ROOT" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    echo "✓ Git branch: $BRANCH ($DIRTY uncommitted change(s))"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Report errors
if [ ${#ERRORS[@]} -gt 0 ]; then
    echo ""
    echo "❌ Environment issues found:"
    for err in "${ERRORS[@]}"; do
        echo "   → $err"
    done
    echo ""
    echo "Fix these before proceeding."
    exit 1
fi

echo "✅ Environment ready — all checks passed"
