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

source "$CONDA_BASE/etc/profile.d/conda.sh"

# ── Check the env exists ──────────────────────────────────────────────────────
if ! conda env list | grep -qE "^${ENV_NAME}[[:space:]]"; then
    echo "Conda env '${ENV_NAME}' not found."
    echo "Create it with:  conda env create -f \"${SCRIPT_DIR}/environment.yml\""
    echo "Then re-run this script."
    exit 1
fi

conda activate "$ENV_NAME"

exec python3 "${SCRIPT_DIR}/faraday_explorer.py" "$@"
