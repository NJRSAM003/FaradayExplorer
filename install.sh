#!/usr/bin/env bash
# QU Viewer — one-time install helper.
# Run once after cloning:  bash install.sh [conda_env_name]
#
# What it does:
#   1. Creates (or updates) the conda environment from environment.yml
#   2. Installs a .desktop launcher so the app appears in your app menu
#   3. Makes the launcher script executable

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="${1:-qu_viewer}"

echo "=== QU Viewer installer ==================================="
echo "Install directory : $SCRIPT_DIR"
echo "Conda environment : $ENV_NAME"
echo "==========================================================="

# ── 1. Create / update conda env ─────────────────────────────────────────────
find_conda() {
    for p in \
        "$HOME/anaconda3" "$HOME/miniconda3" "$HOME/miniforge3" \
        "$HOME/mambaforge" "/opt/anaconda3" "/opt/miniconda3" \
        "/usr/local/anaconda3" "/usr/local/miniconda3"
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

if conda env list | grep -qE "^${ENV_NAME}[[:space:]]"; then
    echo "[1/3] Conda env '$ENV_NAME' already exists — updating..."
    conda env update -n "$ENV_NAME" -f "$SCRIPT_DIR/environment.yml" --prune
else
    echo "[1/3] Creating conda env '$ENV_NAME'..."
    conda env create -n "$ENV_NAME" -f "$SCRIPT_DIR/environment.yml"
fi

# ── 2. Write .desktop file with correct absolute paths ───────────────────────
echo "[2/3] Installing desktop entry..."
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

sed "s|Exec=.*|Exec=${SCRIPT_DIR}/launch_qu_viewer.sh ${ENV_NAME}|g" \
    "$SCRIPT_DIR/qu_viewer.desktop" > "$DESKTOP_DIR/qu_viewer.desktop"

# ── 3. Permissions ───────────────────────────────────────────────────────────
echo "[3/3] Setting permissions..."
chmod +x "$SCRIPT_DIR/launch_qu_viewer.sh"

echo ""
echo "Done!  Launch QU Viewer with:"
echo "  ${SCRIPT_DIR}/launch_qu_viewer.sh"
echo "  — or find 'QU Viewer' in your application menu."
