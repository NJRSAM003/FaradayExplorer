#!/usr/bin/env bash
# Faraday Explorer launcher.
# Usage:
#   ./launch_faraday_explorer.sh                            # GUI mode
#   ./launch_faraday_explorer.sh FDF.fits I.fits Q.fits U.fits freq.dat   # CLI mode
#   ./launch_faraday_explorer.sh --env narnia [args...]     # use a non-default env
# Default conda env name: faraday_explorer  (matches environment.yml)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="faraday_explorer"

# Parse an optional --env/-e flag (must come first)
if [ "$1" = "--env" ] || [ "$1" = "-e" ]; then
    ENV_NAME="$2"
    shift 2
elif [ -n "$1" ] && [ ! -e "$1" ] && [[ "$1" != *.fits ]] && [[ "$1" != *.FITS ]] \
     && [[ "$1" != *.dat ]] && [[ "$1" != *.txt ]] && [[ "$1" != -* ]]; then
    # Backward-compatible: first non-file token is treated as the env name
    ENV_NAME="$1"
    shift
fi

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
