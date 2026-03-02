#!/usr/bin/env bash
# Linepipe uninstaller — removes the app and its desktop/icon assets
set -euo pipefail

info()    { echo -e "\033[0;34m[INFO]\033[0m  $*"; }
success() { echo -e "\033[0;32m[OK]\033[0m    $*"; }
warn()    { echo -e "\033[0;33m[WARN]\033[0m  $*"; }

echo "============================================"
echo "  Linepipe Uninstaller - 1.0"
echo "============================================"
echo ""

# ---------------------------------------------------------------------------
# Uninstall Python package
# ---------------------------------------------------------------------------
for pip_cmd in pip3.12 pip3.11 pip3 pip; do
    if command -v "$pip_cmd" &>/dev/null; then
        info "Uninstalling linepipe via $pip_cmd…"
        "$pip_cmd" uninstall -y linepipe 2>/dev/null || true
        break
    fi
done

# ---------------------------------------------------------------------------
# Remove desktop integration
# ---------------------------------------------------------------------------
info "Removing .desktop file…"
rm -f "$HOME/.local/share/applications/io.github.torcken.linepipe.desktop"

info "Removing metainfo…"
rm -f "$HOME/.local/share/metainfo/io.github.torcken.linepipe.metainfo.xml"

info "Removing icons…"
for size in 16 22 24 32 48 64 96 128 256 512 1024; do
    rm -f "$HOME/.local/share/icons/hicolor/${size}x${size}/apps/io.github.torcken.linepipe.png"
done

# Update caches
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# Optional: remove config
# ---------------------------------------------------------------------------
if [ -d "$HOME/.config/linepipe" ]; then
    read -rp "Remove Linepipe config (~/.config/linepipe/)? [y/N] " ans
    case "$ans" in
        [Yy]*)
            rm -rf "$HOME/.config/linepipe"
            info "Config removed."
            ;;
        *)
            info "Config kept at ~/.config/linepipe/"
            ;;
    esac
fi

echo ""
success "Linepipe has been uninstalled."
