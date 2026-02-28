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

"""Dialogs for Linepipe — Install, Inject, Run."""

from __future__ import annotations

from typing import Callable, Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk


class InstallDialog(Adw.Dialog):
    """Dialog for `pipx install` with package name, version spec, and options."""

    def __init__(
        self,
        parent: Gtk.Widget,
        on_install: Callable[[str, str, bool, str], None],
        initial_name: str = "",
    ) -> None:
        super().__init__()
        self.set_title("Install Package")
        self.set_content_width(420)

        self._on_install = on_install

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Content
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(8)
        content.set_margin_bottom(16)

        prefs_group = Adw.PreferencesGroup()
        prefs_group.set_title("Package")

        # Package name row
        self._name_row = Adw.EntryRow()
        self._name_row.set_title("Package Name")
        if initial_name:
            self._name_row.set_text(initial_name)
        prefs_group.add(self._name_row)

        # Version spec row
        self._ver_row = Adw.EntryRow()
        self._ver_row.set_title("Version Spec (optional, e.g. ==1.2.3)")
        prefs_group.add(self._ver_row)

        content.append(prefs_group)

        options_group = Adw.PreferencesGroup()
        options_group.set_title("Options")
        options_group.set_margin_top(16)

        # Include dependencies switch
        self._include_deps_row = Adw.SwitchRow()
        self._include_deps_row.set_title("Include Dependencies")
        self._include_deps_row.set_subtitle("Pass --include-deps to pipx")
        options_group.add(self._include_deps_row)

        content.append(options_group)

        # Python path
        py_group = Adw.PreferencesGroup()
        py_group.set_margin_top(16)

        self._python_row = Adw.EntryRow()
        self._python_row.set_title("Custom Python Path (optional)")
        py_group.add(self._python_row)

        content.append(py_group)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_margin_top(16)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.close())
        btn_box.append(cancel_btn)

        install_btn = Gtk.Button(label="Install")
        install_btn.add_css_class("suggested-action")
        install_btn.connect("clicked", self._on_install_clicked)
        btn_box.append(install_btn)

        content.append(btn_box)

        toolbar_view.set_content(content)
        self.set_child(toolbar_view)

        self._name_row.grab_focus()

    def _on_install_clicked(self, _btn: Gtk.Button) -> None:
        name = self._name_row.get_text().strip()
        if not name:
            self._name_row.add_css_class("error")
            return
        self._name_row.remove_css_class("error")

        ver_spec = self._ver_row.get_text().strip()
        include_deps = self._include_deps_row.get_active()
        python_path = self._python_row.get_text().strip()

        self.close()
        self._on_install(name, ver_spec, include_deps, python_path)


class InjectDialog(Adw.Dialog):
    """Dialog for `pipx inject <pkg> <dep1> <dep2...>`."""

    def __init__(
        self,
        parent: Gtk.Widget,
        pkg_name: str,
        on_inject: Callable[[list[str]], None],
    ) -> None:
        super().__init__()
        self.set_title(f"Inject into {pkg_name}")
        self.set_content_width(400)

        self._on_inject = on_inject

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(8)
        content.set_margin_bottom(16)

        prefs_group = Adw.PreferencesGroup()
        prefs_group.set_title("Dependencies")
        prefs_group.set_description(
            f"Enter one or more package names to inject into '{pkg_name}'. "
            "Separate multiple packages with spaces or commas."
        )

        self._deps_row = Adw.EntryRow()
        self._deps_row.set_title("Package Names")
        prefs_group.add(self._deps_row)

        content.append(prefs_group)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_margin_top(16)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.close())
        btn_box.append(cancel_btn)

        inject_btn = Gtk.Button(label="Inject")
        inject_btn.add_css_class("suggested-action")
        inject_btn.connect("clicked", self._on_inject_clicked)
        btn_box.append(inject_btn)

        content.append(btn_box)

        toolbar_view.set_content(content)
        self.set_child(toolbar_view)

        self._deps_row.grab_focus()

    def _on_inject_clicked(self, _btn: Gtk.Button) -> None:
        raw = self._deps_row.get_text().strip()
        if not raw:
            self._deps_row.add_css_class("error")
            return
        self._deps_row.remove_css_class("error")

        # Split by whitespace or comma
        import re
        deps = [d.strip() for d in re.split(r"[\s,]+", raw) if d.strip()]
        self.close()
        self._on_inject(deps)


class RunDialog(Adw.Dialog):
    """Dialog for `pipx run <app>` — shows available apps for selected package."""

    def __init__(
        self,
        parent: Gtk.Widget,
        pkg_name: str,
        apps: list[str],
        on_run: Callable[[str, list[str]], None],
    ) -> None:
        super().__init__()
        self.set_title(f"Run App from {pkg_name}")
        self.set_content_width(400)

        self._on_run = on_run

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(8)
        content.set_margin_bottom(16)

        # App selection
        apps_group = Adw.PreferencesGroup()
        apps_group.set_title("Select App")

        self._app_combo = Gtk.DropDown.new_from_strings(apps if apps else [pkg_name])
        self._app_combo.set_margin_top(8)
        self._app_combo.set_margin_bottom(8)
        apps_group.add(self._app_combo)

        content.append(apps_group)

        # Arguments
        args_group = Adw.PreferencesGroup()
        args_group.set_title("Arguments")
        args_group.set_margin_top(12)

        self._args_row = Adw.EntryRow()
        self._args_row.set_title("Extra Arguments (optional)")
        args_group.add(self._args_row)

        content.append(args_group)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_margin_top(16)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.close())
        btn_box.append(cancel_btn)

        run_btn = Gtk.Button(label="Run")
        run_btn.add_css_class("suggested-action")
        run_btn.connect("clicked", self._on_run_clicked)
        btn_box.append(run_btn)

        content.append(btn_box)

        toolbar_view.set_content(content)
        self.set_child(toolbar_view)

    def _on_run_clicked(self, _btn: Gtk.Button) -> None:
        selected = self._app_combo.get_selected()
        model = self._app_combo.get_model()
        app_name = model.get_string(selected) if model else ""

        raw_args = self._args_row.get_text().strip()
        import shlex
        try:
            extra_args = shlex.split(raw_args) if raw_args else []
        except ValueError:
            extra_args = raw_args.split()

        self.close()
        self._on_run(app_name, extra_args)
