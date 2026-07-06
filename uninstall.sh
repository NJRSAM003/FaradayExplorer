#!/usr/bin/env bash
# Faraday Explorer — uninstall helper.
# Run from the repo:  bash uninstall.sh [conda_env_name]
#
# What it does (with confirmation at each step):
#   1. Removes the clickable launcher (.app bundle on macOS / .desktop on Linux)
#   2. Removes the Qt settings cache
#   3. Removes the conda environment created by install.sh
#
# What it does NOT do:
#   - Delete the cloned repository directory (you do that with `rm -rf`)
#   - Touch any FITS / data files you may have produced

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="${1:-faraday_explorer}"
OS="$(uname)"

if [ "$OS" = "Darwin" ]; then
    if [ -d "/Applications/FaradayExplorer.app" ]; then
        APP_DIR="/Applications/FaradayExplorer.app"
    else
        APP_DIR="$HOME/Applications/FaradayExplorer.app"
    fi
    SETTINGS_PATH="$HOME/Library/Preferences/com.FaradayExplorer.FaradayExplorer.plist"
    LAUNCHER_LABEL="App bundle : $APP_DIR"
    SETTINGS_LABEL="Qt settings: $SETTINGS_PATH"
else
    LAUNCHER_LABEL="Desktop entry: ~/.local/share/applications/faraday_explorer.desktop"
    SETTINGS_LABEL="Qt settings  : ~/.config/AmaniAstro/"
fi

echo "=== Faraday Explorer uninstaller ===================================="
echo "Conda environment to remove : $ENV_NAME"
echo "$LAUNCHER_LABEL"
echo "$SETTINGS_LABEL"
echo "Repo directory ($SCRIPT_DIR) will NOT be deleted."
echo "====================================================================="

read -r -p "Proceed with uninstall? [y/N] " ans
case "$ans" in
    [Yy]|[Yy][Ee][Ss]) ;;
    *) echo "Aborted."; exit 0 ;;
esac

# ── 1. Remove launcher ───────────────────────────────────────────────────────
echo "[1/3] Removing launcher..."
if [ "$OS" = "Darwin" ]; then
    rm -rf "$APP_DIR"
else
    rm -f "$HOME/.local/share/applications/faraday_explorer.desktop"
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    rm -f "$HOME/.local/share/icons/hicolor/512x512/apps/faraday_explorer.png"
    gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

# ── 2. Remove Qt settings cache ──────────────────────────────────────────────
echo "[2/3] Removing settings cache..."
if [ "$OS" = "Darwin" ]; then
    rm -f "$SETTINGS_PATH"
else
    rm -rf "$HOME/.config/AmaniAstro"
fi

# ── 3. Remove conda env ──────────────────────────────────────────────────────
echo "[3/3] Removing conda environment '$ENV_NAME'..."
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
if [ -n "$CONDA_BASE" ]; then
    source "$CONDA_BASE/etc/profile.d/conda.sh"
    if conda env list | grep -qE "^${ENV_NAME}[[:space:]]"; then
        conda env remove -n "$ENV_NAME" -y
    else
        echo "  (env '$ENV_NAME' not found — nothing to remove)"
    fi
else
    echo "  (conda not found — skipping env removal; do it manually if needed)"
fi

echo ""
echo "Done. To finish uninstall, delete the repo directory if you wish:"
echo "  rm -rf $SCRIPT_DIR"
