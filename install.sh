#!/usr/bin/env bash
# Faraday Explorer — one-time install helper.
# Run once after cloning:  bash install.sh [conda_env_name]
#
# What it does:
#   1. Creates (or updates) the conda environment from environment.yml
#   2. Installs a clickable launcher:
#      - Linux : .desktop entry  (appears in app menu)
#      - macOS : .app bundle     (~/Applications/FaradayExplorer.app)
#   3. Makes the launcher script executable

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="${1:-faraday_explorer}"
OS="$(uname)"

echo "=== Faraday Explorer installer ==================================="
echo "Install directory : $SCRIPT_DIR"
echo "Conda environment : $ENV_NAME"
echo "Platform          : $OS"
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

# ── 2. Platform-specific launcher registration ────────────────────────────────
if [ "$OS" = "Darwin" ]; then
    # macOS: build a .app bundle in ~/Applications/
    echo "[2/3] Creating macOS app bundle..."

    APP_DIR="$HOME/Applications/FaradayExplorer.app"
    mkdir -p "$APP_DIR/Contents/MacOS"
    mkdir -p "$APP_DIR/Contents/Resources"

    # Convert FEIcon.png → FEIcon.icns (requires sips + iconutil, both ship with macOS)
    ICONSET="$(mktemp -d)/FEIcon.iconset"
    mkdir -p "$ICONSET"
    for size in 16 32 128 256 512; do
        sips -z $size $size "$SCRIPT_DIR/FEIcon.png" \
             --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
    done
    sips -z 32   32   "$SCRIPT_DIR/FEIcon.png" --out "$ICONSET/icon_16x16@2x.png"   >/dev/null
    sips -z 64   64   "$SCRIPT_DIR/FEIcon.png" --out "$ICONSET/icon_32x32@2x.png"   >/dev/null
    sips -z 256  256  "$SCRIPT_DIR/FEIcon.png" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
    sips -z 512  512  "$SCRIPT_DIR/FEIcon.png" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
    sips -z 1024 1024 "$SCRIPT_DIR/FEIcon.png" --out "$ICONSET/icon_512x512@2x.png" 2>/dev/null \
        || cp "$ICONSET/icon_512x512.png" "$ICONSET/icon_512x512@2x.png"
    iconutil -c icns "$ICONSET" -o "$APP_DIR/Contents/Resources/FEIcon.icns"
    rm -rf "$(dirname "$ICONSET")"

    # Info.plist
    cat > "$APP_DIR/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>FaradayExplorer</string>
    <key>CFBundleDisplayName</key>
    <string>Faraday Explorer</string>
    <key>CFBundleExecutable</key>
    <string>FaradayExplorer</string>
    <key>CFBundleIconFile</key>
    <string>FEIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.faradayexplorer.app</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
PLIST

    # Executable wrapper inside the bundle
    cat > "$APP_DIR/Contents/MacOS/FaradayExplorer" << LAUNCHER
#!/usr/bin/env bash
exec "${SCRIPT_DIR}/launch_faraday_explorer.sh" ${ENV_NAME} "\$@"
LAUNCHER
    chmod +x "$APP_DIR/Contents/MacOS/FaradayExplorer"

    echo ""
    echo "Done!  FaradayExplorer.app is in ~/Applications."
    echo "  Open it with:  open ~/Applications/FaradayExplorer.app"
    echo "  Or drag it from Finder to your Dock for one-click access."
    echo "  Note: the .app references this directory — don't move the repo"
    echo "  without re-running install.sh."

else
    # Linux: install icon + .desktop entry
    echo "[2/4] Installing app icon..."
    ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"
    mkdir -p "$ICON_DIR"
    cp "$SCRIPT_DIR/FEIcon.png" "$ICON_DIR/faraday_explorer.png"
    gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

    echo "[3/4] Installing desktop entry..."
    DESKTOP_DIR="$HOME/.local/share/applications"
    mkdir -p "$DESKTOP_DIR"

    sed -e "s|Exec=.*|Exec=${SCRIPT_DIR}/launch_faraday_explorer.sh ${ENV_NAME}|g" \
        -e "s|Icon=.*|Icon=${SCRIPT_DIR}/FEIcon.png|g" \
        "$SCRIPT_DIR/faraday_explorer.desktop" > "$DESKTOP_DIR/faraday_explorer.desktop"

    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

    echo "[4/4] Setting permissions..."
    chmod +x "$SCRIPT_DIR/launch_faraday_explorer.sh"

    echo ""
    echo "Done!  Launch Faraday Explorer with:"
    echo "  ${SCRIPT_DIR}/launch_faraday_explorer.sh"
    echo "  — or find 'Faraday Explorer' in your application menu."
fi

# ── 3. Ensure launcher is executable on both platforms ───────────────────────
chmod +x "$SCRIPT_DIR/launch_faraday_explorer.sh"
