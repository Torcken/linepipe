# Copyright (C) 2025  Torcken
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Made with 🤍 by Torcken

"""Detail panel — right pane showing package info and action buttons."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GObject", "2.0")
from gi.repository import Adw, GObject, Gtk


class DetailPanel(Gtk.ScrolledWindow):
    """Right pane showing package details and contextual action buttons."""

    __gsignals__ = {
        "install-requested": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "uninstall-requested": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "upgrade-requested": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "inject-requested": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "run-requested": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self) -> None:
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_min_content_width(280)

        self._current_name: str = ""
        self._is_pypi_result = False

        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._box.set_margin_start(16)
        self._box.set_margin_end(16)
        self._box.set_margin_top(16)
        self._box.set_margin_bottom(16)
        self.set_child(self._box)

        self.show_empty()

    # ------------------------------------------------------------------
    # Public state methods
    # ------------------------------------------------------------------

    def show_empty(self) -> None:
        self._clear()
        status_page = Adw.StatusPage()
        status_page.set_icon_name("package-x-generic-symbolic")
        status_page.set_title("No Package Selected")
        status_page.set_description("Select a package to view details")
        status_page.set_vexpand(True)
        self._box.append(status_page)

    def show_search_hint(self) -> None:
        self._clear()
        status_page = Adw.StatusPage()
        status_page.set_icon_name("system-search-symbolic")
        status_page.set_title("Search PyPI")
        status_page.set_description(
            'Type a package name in the search bar above, then press Enter '
            'or click "Search PyPI" to look it up.'
        )
        status_page.set_vexpand(True)
        self._box.append(status_page)

    def show_loading(self, name: str) -> None:
        self._clear()
        spinner = Gtk.Spinner()
        spinner.set_spinning(True)
        spinner.set_size_request(32, 32)
        spinner.set_halign(Gtk.Align.CENTER)
        spinner.set_margin_top(48)
        self._box.append(spinner)

        label = Gtk.Label(label=f"Loading {name}…")
        label.add_css_class("dim-label")
        label.set_margin_top(12)
        self._box.append(label)

    def show_package(self, pkg, is_pypi_result: bool = False) -> None:
        """Show details for an installed PackageItem or a PyPI info dict."""
        self._clear()
        self._is_pypi_result = is_pypi_result

        if is_pypi_result:
            self._show_pypi_result(pkg)
        else:
            self._show_installed_package(pkg)

    # ------------------------------------------------------------------
    # Internal renderers
    # ------------------------------------------------------------------

    def _show_installed_package(self, pkg) -> None:
        from linepipe.package_list import PackageItem
        self._current_name = pkg.name

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        icon = Gtk.Image.new_from_icon_name("package-x-generic-symbolic")
        icon.set_pixel_size(48)
        icon.add_css_class("dim-label")
        header.append(icon)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_box.set_valign(Gtk.Align.CENTER)
        name_label = Gtk.Label(label=pkg.name)
        name_label.set_xalign(0)
        name_label.add_css_class("title-2")
        name_label.set_wrap(True)
        title_box.append(name_label)

        ver_text = pkg.version or "unknown"
        if pkg.status == "outdated" and pkg.latest_version:
            ver_text += f" → {pkg.latest_version}"
        ver_label = Gtk.Label(label=ver_text)
        ver_label.set_xalign(0)
        ver_label.add_css_class("dim-label")
        title_box.append(ver_label)

        header.append(title_box)
        self._box.append(header)

        self._box.append(self._make_separator())

        # Info group
        info_group = Adw.PreferencesGroup()
        info_group.set_margin_top(12)

        if pkg.python_version:
            py_row = Adw.ActionRow()
            py_row.set_title("Python")
            py_row.set_subtitle(pkg.python_version)
            info_group.add(py_row)

        if pkg.venv_location:
            venv_row = Adw.ActionRow()
            venv_row.set_title("Venv Location")
            venv_row.set_subtitle(pkg.venv_location)
            venv_row.set_subtitle_selectable(True)
            info_group.add(venv_row)

        apps_count = len(pkg.apps)
        apps_row = Adw.ActionRow()
        apps_row.set_title("Exposed Apps")
        apps_row.set_subtitle(
            ", ".join(pkg.apps) if pkg.apps else "None"
        )
        info_group.add(apps_row)

        if pkg.injected:
            inj_row = Adw.ActionRow()
            inj_row.set_title("Injected Packages")
            inj_row.set_subtitle(", ".join(pkg.injected))
            info_group.add(inj_row)

        self._box.append(info_group)

        # Action buttons
        self._box.append(self._make_separator())

        actions_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        actions_box.set_margin_top(12)

        upgrade_btn = Gtk.Button(label="Upgrade")
        upgrade_btn.set_icon_name("software-update-available-symbolic")
        upgrade_btn.set_halign(Gtk.Align.FILL)
        upgrade_btn.connect("clicked", lambda _: self.emit("upgrade-requested", pkg.name))
        actions_box.append(upgrade_btn)

        inject_btn = Gtk.Button(label="Inject Package")
        inject_btn.set_icon_name("list-add-symbolic")
        inject_btn.set_halign(Gtk.Align.FILL)
        inject_btn.connect("clicked", lambda _: self.emit("inject-requested", pkg.name))
        actions_box.append(inject_btn)

        if pkg.apps:
            run_btn = Gtk.Button(label="Run App")
            run_btn.set_icon_name("media-playback-start-symbolic")
            run_btn.set_halign(Gtk.Align.FILL)
            run_btn.connect("clicked", lambda _: self.emit("run-requested", pkg.name))
            actions_box.append(run_btn)

        uninstall_btn = Gtk.Button(label="Uninstall")
        uninstall_btn.set_icon_name("user-trash-symbolic")
        uninstall_btn.set_halign(Gtk.Align.FILL)
        uninstall_btn.add_css_class("destructive-action")
        uninstall_btn.connect("clicked", lambda _: self.emit("uninstall-requested", pkg.name))
        actions_box.append(uninstall_btn)

        self._box.append(actions_box)

    def _show_pypi_result(self, info: dict) -> None:
        name = info.get("name", "")
        self._current_name = name

        # Header
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        name_label = Gtk.Label(label=name)
        name_label.set_xalign(0)
        name_label.add_css_class("title-2")
        header_box.append(name_label)

        if info.get("version"):
            ver_label = Gtk.Label(label=f"Latest: {info['version']}")
            ver_label.set_xalign(0)
            ver_label.add_css_class("dim-label")
            header_box.append(ver_label)

        pypi_badge = Gtk.Label(label="PyPI")
        pypi_badge.add_css_class("status-badge")
        pypi_badge.add_css_class("badge-unknown")
        pypi_badge.set_xalign(0)
        pypi_badge.set_margin_top(4)
        header_box.append(pypi_badge)

        self._box.append(header_box)
        self._box.append(self._make_separator())

        # Info group
        info_group = Adw.PreferencesGroup()
        info_group.set_margin_top(12)

        if info.get("summary"):
            summary_row = Adw.ActionRow()
            summary_row.set_title("Summary")
            summary_row.set_subtitle(info["summary"])
            info_group.add(summary_row)

        if info.get("author"):
            author_row = Adw.ActionRow()
            author_row.set_title("Author")
            author_row.set_subtitle(info["author"])
            info_group.add(author_row)

        if info.get("license"):
            lic_row = Adw.ActionRow()
            lic_row.set_title("License")
            lic_row.set_subtitle(info["license"])
            info_group.add(lic_row)

        if info.get("requires_python"):
            py_row = Adw.ActionRow()
            py_row.set_title("Requires Python")
            py_row.set_subtitle(info["requires_python"])
            info_group.add(py_row)

        if info.get("home_page"):
            hp_row = Adw.ActionRow()
            hp_row.set_title("Homepage")
            hp_row.set_subtitle(info["home_page"])
            hp_row.set_subtitle_selectable(True)
            hp_row.set_activatable(True)
            hp_row.connect(
                "activated",
                lambda _row, url=info["home_page"]: self._open_url(url),
            )
            hp_row.add_suffix(Gtk.Image.new_from_icon_name("external-link-symbolic"))
            info_group.add(hp_row)

        pypi_url = f"https://pypi.org/project/{name}/"
        pypi_row = Adw.ActionRow()
        pypi_row.set_title("PyPI Page")
        pypi_row.set_subtitle(pypi_url)
        pypi_row.set_subtitle_selectable(True)
        pypi_row.set_activatable(True)
        pypi_row.connect(
            "activated",
            lambda _row, url=pypi_url: self._open_url(url),
        )
        pypi_row.add_suffix(Gtk.Image.new_from_icon_name("external-link-symbolic"))
        info_group.add(pypi_row)

        self._box.append(info_group)

        self._box.append(self._make_separator())

        install_btn = Gtk.Button(label=f"Install {name}")
        install_btn.add_css_class("suggested-action")
        install_btn.set_halign(Gtk.Align.FILL)
        install_btn.set_margin_top(12)
        install_btn.connect("clicked", lambda _: self.emit("install-requested", name))
        self._box.append(install_btn)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _clear(self) -> None:
        child = self._box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self._box.remove(child)
            child = next_child
        self._current_name = ""
        self._is_pypi_result = False

    def _make_separator(self) -> Gtk.Separator:
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(12)
        sep.set_margin_bottom(4)
        return sep

    def _open_url(self, url: str) -> None:
        import subprocess
        try:
            subprocess.Popen(
                ["xdg-open", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass

    @property
    def current_name(self) -> str:
        return self._current_name
