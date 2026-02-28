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

"""Preferences dialog and config helpers for Linepipe."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from linepipe.utils import load_prefs, save_prefs


def apply_color_scheme(scheme: str) -> None:
    """Apply color scheme using Adw.StyleManager."""
    manager = Adw.StyleManager.get_default()
    if scheme == "light":
        manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
    elif scheme == "dark":
        manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
    else:
        manager.set_color_scheme(Adw.ColorScheme.DEFAULT)


class PreferencesDialog(Adw.PreferencesDialog):
    """Application preferences using Adw.PreferencesDialog."""

    def __init__(self) -> None:
        super().__init__()
        self.set_title("Preferences")

        self._prefs = load_prefs()

        # ---- General page ----
        general_page = Adw.PreferencesPage()
        general_page.set_title("General")
        general_page.set_icon_name("preferences-system-symbolic")
        self.add(general_page)

        # Color scheme group
        appearance_group = Adw.PreferencesGroup()
        appearance_group.set_title("Appearance")
        general_page.add(appearance_group)

        self._scheme_row = Adw.ComboRow()
        self._scheme_row.set_title("Color Scheme")
        schemes = Gtk.StringList.new(["System", "Light", "Dark"])
        self._scheme_row.set_model(schemes)

        scheme = self._prefs.get("color_scheme", "system")
        idx = {"system": 0, "light": 1, "dark": 2}.get(scheme, 0)
        self._scheme_row.set_selected(idx)
        self._scheme_row.connect("notify::selected", self._on_scheme_changed)
        appearance_group.add(self._scheme_row)

        # Install options group
        install_group = Adw.PreferencesGroup()
        install_group.set_title("Install Defaults")
        general_page.add(install_group)

        self._include_deps_row = Adw.SwitchRow()
        self._include_deps_row.set_title("Include Dependencies")
        self._include_deps_row.set_subtitle("Pass --include-deps by default")
        self._include_deps_row.set_active(self._prefs.get("include_deps", False))
        self._include_deps_row.connect("notify::active", self._on_include_deps_changed)
        install_group.add(self._include_deps_row)

        self._prerelease_row = Adw.SwitchRow()
        self._prerelease_row.set_title("Show Pre-release Versions")
        self._prerelease_row.set_subtitle("Include pre-releases when checking for updates")
        self._prerelease_row.set_active(self._prefs.get("show_prerelease", False))
        self._prerelease_row.connect("notify::active", self._on_prerelease_changed)
        install_group.add(self._prerelease_row)

        # ---- pipx page ----
        pipx_page = Adw.PreferencesPage()
        pipx_page.set_title("pipx")
        pipx_page.set_icon_name("utilities-terminal-symbolic")
        self.add(pipx_page)

        pipx_group = Adw.PreferencesGroup()
        pipx_group.set_title("pipx Path")
        pipx_group.set_description(
            "Leave empty to auto-detect. Specify an absolute path to override."
        )
        pipx_page.add(pipx_group)

        self._pipx_path_row = Adw.EntryRow()
        self._pipx_path_row.set_title("Custom pipx Path")
        self._pipx_path_row.set_text(self._prefs.get("pipx_path", ""))
        self._pipx_path_row.connect("changed", self._on_pipx_path_changed)
        pipx_group.add(self._pipx_path_row)

        docs_group = Adw.PreferencesGroup()
        docs_group.set_title("Resources")
        pipx_page.add(docs_group)

        docs_row = Adw.ActionRow()
        docs_row.set_title("pipx Documentation")
        docs_row.set_subtitle("https://pipx.pypa.io/")
        docs_row.set_activatable(True)
        docs_row.connect("activated", self._on_docs_clicked)
        docs_icon = Gtk.Image.new_from_icon_name("external-link-symbolic")
        docs_row.add_suffix(docs_icon)
        docs_group.add(docs_row)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_scheme_changed(self, row: Adw.ComboRow, _param) -> None:
        idx = row.get_selected()
        scheme = ["system", "light", "dark"][idx]
        self._prefs["color_scheme"] = scheme
        save_prefs(self._prefs)
        apply_color_scheme(scheme)

    def _on_include_deps_changed(self, row: Adw.SwitchRow, _param) -> None:
        self._prefs["include_deps"] = row.get_active()
        save_prefs(self._prefs)

    def _on_prerelease_changed(self, row: Adw.SwitchRow, _param) -> None:
        self._prefs["show_prerelease"] = row.get_active()
        save_prefs(self._prefs)

    def _on_pipx_path_changed(self, row: Adw.EntryRow) -> None:
        self._prefs["pipx_path"] = row.get_text().strip()
        save_prefs(self._prefs)
        from linepipe.pipx_interface import invalidate_pipx_cache
        invalidate_pipx_cache()

    def _on_docs_clicked(self, _row) -> None:
        import subprocess
        try:
            subprocess.Popen(
                ["xdg-open", "https://pipx.pypa.io/"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass
