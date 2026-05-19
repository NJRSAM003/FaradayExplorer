#!/usr/bin/env bash
# Faraday Explorer — one-time install helper.
# Run once after cloning:  bash install.sh [conda_env_name]
#
# What it does:
#   1. Creates (or updates) the conda environment from environment.yml
#   2. Installs the app icon to ~/.local/share/icons/
#   3. Installs a .desktop launcher so the app appears in your app menu
#   4. Makes the launcher script executable

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="${1:-faraday_explorer}"

echo "=== Faraday Explorer installer ==================================="
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

# ── 2. Install app icon ───────────────────────────────────────────────────────
echo "[2/4] Installing app icon..."
ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"
mkdir -p "$ICON_DIR"
cp "$SCRIPT_DIR/FEIcon.png" "$ICON_DIR/faraday_explorer.png"
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

# ── 3. Write .desktop file with correct absolute paths ───────────────────────
echo "[3/4] Installing desktop entry..."
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

sed "s|Exec=.*|Exec=${SCRIPT_DIR}/launch_faraday_explorer.sh ${ENV_NAME}|g" \
    "$SCRIPT_DIR/faraday_explorer.desktop" > "$DESKTOP_DIR/faraday_explorer.desktop"

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

# ── 4. Permissions ───────────────────────────────────────────────────────────
echo "[4/4] Setting permissions..."
chmod +x "$SCRIPT_DIR/launch_faraday_explorer.sh"

echo ""
echo "Done!  Launch Faraday Explorer with:"
echo "  ${SCRIPT_DIR}/launch_faraday_explorer.sh"
echo "  — or find 'Faraday Explorer' in your application menu."
