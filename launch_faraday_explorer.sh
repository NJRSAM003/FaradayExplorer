#!/usr/bin/env bash
# Faraday Explorer launcher.
# Usage:  ./launch_faraday_explorer.sh [conda_env_name]
# Default env name: faraday_explorer  (matches environment.yml)
# Override:         ./launch_faraday_explorer.sh narnia

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="${1:-faraday_explorer}"

# ── Locate conda ──────────────────────────────────────────────────────────────
find_conda() {
    for p in \
        "$HOME/anaconda3" \
        "$HOME/miniconda3" \
        "$HOME/miniforge3" \
        "$HOME/mambaforge" \
        "/opt/anaconda3" \
        "/opt/miniconda3" \
        "/usr/local/anaconda3" \
        "/usr/local/miniconda3"
    do
        [ -f "$p/etc/profile.d/conda.sh" ] && { echo "$p"; return; }
    done
}

CONDA_BASE="$(find_conda)"
if [ -z "$CONDA_BASE" ]; then
    echo "ERROR: conda not found. Install Anaconda or Miniconda first." >&2
    exit 1
fi

# Use the env's Python directly — works in non-interactive shells (desktop launchers)
ENV_PYTHON="$CONDA_BASE/envs/$ENV_NAME/bin/python3"

if [ ! -x "$ENV_PYTHON" ]; then
    echo "ERROR: Conda env '$ENV_NAME' not found at $CONDA_BASE/envs/$ENV_NAME" >&2
    echo "Create it with:  conda env create -f \"${SCRIPT_DIR}/environment.yml\"" >&2
    exit 1
fi

exec "$ENV_PYTHON" "${SCRIPT_DIR}/faraday_explorer.py" "$@"
