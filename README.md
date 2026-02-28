# Linepipe

A modern GTK4/Adwaita graphical interface for [pipx](https://pipx.pypa.io/) on Linux.

Linepipe lets you install, upgrade, uninstall, inject, and run pipx-managed Python
applications through a native GNOME interface — no terminal required.

---

## Features

- **List installed packages** with version, Python version, exposed apps, and injected deps
- **Install** packages from PyPI with optional version pinning, `--include-deps`, and custom Python
- **Upgrade** individual packages or all at once (`pipx upgrade-all`)
- **Uninstall** with confirmation dialog
- **Inject / Uninject** extra dependencies into existing pipx venvs
- **Run** exposed application binaries with optional arguments
- **Outdated detection** — checks PyPI JSON API in the background, highlights outdated packages
- **Search PyPI** — filter installed list instantly; press Enter for exact PyPI lookup
- **Desktop notifications** on operation success/failure
- **GNOME HIG compliant** — Adwaita styling, toast notifications, dark/light mode

---

## Requirements

- Linux with GTK 4.0+ and libadwaita 1.0+
- Python 3.11+
- PyGObject 3.44+
- [pipx](https://pipx.pypa.io/) (to actually manage packages)

---

## Installation

### Quick install (recommended)

```bash
git clone https://github.com/Torcken/linepipe.git
cd linepipe
bash install.sh
```

The installer will:
1. Install GTK4/Adwaita system dependencies for your distro
2. Install Linepipe with pip
3. Install the `.desktop` file and icons for your launcher

### Manual pip install

```bash
pip install --user .
```

Then copy the desktop/icon files manually:

```bash
cp data/io.github.torcken.linepipe.desktop ~/.local/share/applications/
for size in 16 22 24 32 48 64 96 128 256 512 1024; do
    mkdir -p ~/.local/share/icons/hicolor/${size}x${size}/apps
    cp data/icons/hicolor/${size}x${size}/apps/io.github.torcken.linepipe.png \
       ~/.local/share/icons/hicolor/${size}x${size}/apps/
done
gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor
```

---

## Uninstall

```bash
bash uninstall.sh
```

---

## Usage

Launch from your application menu or run:

```bash
linepipe
```

### Keyboard shortcuts

| Shortcut       | Action                    |
|----------------|---------------------------|
| `Ctrl+R` / `F5`| Refresh installed list    |
| `Ctrl+F`       | Focus search bar          |
| `Ctrl+P`       | Open Preferences          |
| `Ctrl+I`       | Open Install dialog       |
| `?`            | Show keyboard shortcuts   |
| `Ctrl+Q`       | Quit                      |

---

## Configuration

Preferences are stored in `~/.config/linepipe/config.json`:

| Setting | Default | Description |
|---------|---------|-------------|
| `pipx_path` | `""` | Custom path to pipx executable (auto-detect if empty) |
| `color_scheme` | `"system"` | `"system"` / `"light"` / `"dark"` |
| `include_deps` | `false` | Default `--include-deps` for installs |
| `show_prerelease` | `false` | Include pre-releases when checking updates |

---

## Architecture

Linepipe is a faithful adaptation of [Linebrew](https://github.com/Torcken/linebrew),
targeting pipx instead of Homebrew.

| Module | Responsibility |
|--------|---------------|
| `application.py` | `Adw.Application` subclass, CSS loading, global actions |
| `window.py` | Main window — sidebar, package list, detail pane |
| `pipx_interface.py` | All subprocess wrappers for pipx CLI |
| `package_list.py` | `Gio.ListStore` → `Gtk.FilterListModel` → `Gtk.ColumnView` |
| `detail_panel.py` | Right pane: package info + action buttons |
| `dialogs.py` | Install / Inject / Run dialogs |
| `progress_dialog.py` | Streaming command output dialog |
| `preferences.py` | `Adw.PreferencesDialog` + config I/O |
| `notifications.py` | Desktop notification helper |
| `utils.py` | Config I/O, version comparison |

**Design decisions:**
- All pipx commands run in daemon threads; GUI updates go through `GLib.idle_add()`
- PyPI version checks run concurrently per-package, updating the list as results arrive
- Session-level cache: PyPI results are applied to the model and not re-fetched until refresh
- `packaging.version.Version` used for version comparison; falls back to tuple comparison
- PyPI queries use `urllib.request` (stdlib) — no `requests` dependency
- `shell=False` everywhere; OSError is caught gracefully

---

## License

GNU General Public License v3.0 or later. See [LICENSE](LICENSE).
