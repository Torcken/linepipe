#!/usr/bin/env bash
# Linepipe installer — installs the app and its desktop/icon assets
set -euo pipefail

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
info()    { echo -e "\033[0;34m[INFO]\033[0m  $*"; }
success() { echo -e "\033[0;32m[OK]\033[0m    $*"; }
warn()    { echo -e "\033[0;33m[WARN]\033[0m  $*"; }
error()   { echo -e "\033[0;31m[ERROR]\033[0m $*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Distro detection
# ---------------------------------------------------------------------------
detect_distro() {
    if [ -f /etc/os-release ]; then
        # shellcheck source=/dev/null
        . /etc/os-release
        echo "${ID:-unknown}"
    else
        echo "unknown"
    fi
}

# ---------------------------------------------------------------------------
# System dependencies (GTK4 + libadwaita + PyGObject)
# ---------------------------------------------------------------------------
install_system_deps() {
    local distro
    distro="$(detect_distro)"
    info "Detected distro: $distro"

    case "$distro" in
        ubuntu|debian|linuxmint|pop)
            info "Installing Linepipe system dependencies via apt…"
            sudo apt-get update -qq
            sudo apt-get install -y --no-install-recommends \
                python3-gi python3-gi-cairo gir1.2-gtk-4.0 \
                gir1.2-adw-1 libadwaita-1-0 \
                python3-pip python3-venv
            ;;
        fedora|rhel|centos|rocky|almalinux)
            info "Installing GTK4/Adwaita system dependencies via dnf…"
            sudo dnf install -y \
                python3-gobject python3-gobject-base \
                gtk4 libadwaita python3-pip
            ;;
        arch|manjaro|endeavouros|garuda)
            info "Installing GTK4/Adwaita system dependencies via pacman…"
            sudo pacman -Sy --noconfirm \
                python-gobject gtk4 libadwaita python-pip
            ;;
        opensuse*|suse*)
            info "Installing Linepipe dependencies via zypper…"
            sudo zypper install -y \
                python3-gobject-cairo gtk4 libadwaita python3-pip
            ;;
        *)
            warn "Unknown distro '$distro'. Skipping automatic dependency install."
            warn "Please install PyGObject, GTK4, and libadwaita manually."
            ;;
    esac
}

# ---------------------------------------------------------------------------
# pipx check
# ---------------------------------------------------------------------------
check_pipx() {
    if command -v pipx &>/dev/null; then
        success "pipx found at $(command -v pipx)"
        return 0
    fi

    warn "pipx not found."
    echo ""
    echo "Linepipe manages pipx packages, but pipx itself is not installed."
    echo "You can install it with:"
    echo "  pip install --user pipx"
    echo "  pipx ensurepath"
    echo "Or visit: https://pipx.pypa.io/"
    echo ""
    read -rp "Continue Linepipe installation without pipx? [y/N] " ans
    case "$ans" in
        [Yy]*) return 0 ;;
        *)     error "Aborting."; exit 1 ;;
    esac
}

# ---------------------------------------------------------------------------
# Install Linepipe
# ---------------------------------------------------------------------------
install_linepipe() {
    info "Installing Linepipe…"
    cd "$SCRIPT_DIR"

    # Prefer system pip to avoid conda/venv pip which blocks --user installs.
    # Try absolute system paths first, then fall back to PATH.
    local pip_cmd=""
    for candidate in /usr/bin/pip3.12 /usr/bin/pip3.11 /usr/bin/pip3 \
                     /usr/local/bin/pip3 pip3.12 pip3.11 pip3 pip; do
        if [ -x "$candidate" ] 2>/dev/null || command -v "$candidate" &>/dev/null; then
            pip_cmd="$candidate"
            break
        fi
    done

    if [ -z "$pip_cmd" ]; then
        error "No pip found. Please install pip and try again."
        exit 1
    fi

    info "Using pip: $pip_cmd"

    # If inside a virtualenv or conda env, --user is not allowed.
    # Detect this and install without --user (into the active env) or
    # explicitly use the system pip with --user.
    local in_venv=0
    if [ -n "${VIRTUAL_ENV:-}" ] || [ -n "${CONDA_DEFAULT_ENV:-}" ]; then
        in_venv=1
        warn "Active virtualenv/conda detected. Trying system pip for --user install."
        # Re-resolve to a system pip outside the venv
        local sys_pip=""
        for candidate in /usr/bin/pip3.12 /usr/bin/pip3.11 /usr/bin/pip3 /usr/local/bin/pip3; do
            if [ -x "$candidate" ]; then
                sys_pip="$candidate"
                break
            fi
        done
        if [ -n "$sys_pip" ]; then
            pip_cmd="$sys_pip"
            in_venv=0
            info "Switched to system pip: $pip_cmd"
        fi
    fi

    if [ "$in_venv" -eq 0 ]; then
        "$pip_cmd" install --user --no-deps --break-system-packages . 2>/dev/null || \
        "$pip_cmd" install --user --no-deps .
    else
        # Last resort: install into the active env without --user
        warn "Could not find system pip outside venv. Installing into active environment."
        "$pip_cmd" install --no-deps .
    fi

    success "Linepipe installed."
}

# ---------------------------------------------------------------------------
# Desktop integration
# ---------------------------------------------------------------------------
install_desktop_files() {
    local apps_dir="$HOME/.local/share/applications"
    local metainfo_dir="$HOME/.local/share/metainfo"
    local icons_base="$HOME/.local/share/icons/hicolor"

    mkdir -p "$apps_dir" "$metainfo_dir"

    info "Installing .desktop file…"
    cp "$SCRIPT_DIR/data/io.github.torcken.linepipe.desktop" "$apps_dir/"

    info "Installing metainfo…"
    cp "$SCRIPT_DIR/data/io.github.torcken.linepipe.metainfo.xml" "$metainfo_dir/"

    info "Installing icons…"
    for size in 16 22 24 32 48 64 96 128 256 512 1024; do
        src="$SCRIPT_DIR/data/icons/hicolor/${size}x${size}/apps/io.github.torcken.linepipe.png"
        dst_dir="$icons_base/${size}x${size}/apps"
        if [ -f "$src" ]; then
            mkdir -p "$dst_dir"
            cp "$src" "$dst_dir/"
        fi
    done

    # Update icon cache if gtk-update-icon-cache is available
    if command -v gtk-update-icon-cache &>/dev/null; then
        gtk-update-icon-cache -f -t "$icons_base" 2>/dev/null || true
    fi

    # Update desktop database
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$apps_dir" 2>/dev/null || true
    fi

    success "Desktop integration installed."
}

# ---------------------------------------------------------------------------
# PATH warning
# ---------------------------------------------------------------------------
check_path() {
    local local_bin="$HOME/.local/bin"
    if [[ ":$PATH:" != *":$local_bin:"* ]]; then
        warn "~/.local/bin is not in your PATH."
        warn "Add the following to your ~/.bashrc or ~/.profile:"
        warn '  export PATH="$HOME/.local/bin:$PATH"'
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo "============================================"
    echo "  Linepipe Installer - 1.0"
    echo "============================================"
    echo ""

    install_system_deps
    check_pipx
    install_linepipe
    install_desktop_files
    check_path

    echo ""
    success "Linepipe installation complete!"
    echo "Run it with: linepipe"
    echo "Or find it in your application launcher."
}

main "$@"
