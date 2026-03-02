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

"""Linepipe Adw.Application — entry point, CSS loading, global actions.

App ID: io.github.torcken.linepipe
"""

from __future__ import annotations

import importlib.resources
import sys
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")
from gi.repository import Adw, Gio, Gtk

from linepipe import __app_id__, __version__
from linepipe.preferences import PreferencesDialog, apply_color_scheme, load_prefs
from linepipe.window import MainWindow


class LinepipeApp(Adw.Application):
    """Top-level application object."""

    def __init__(self) -> None:
        super().__init__(
            application_id=__app_id__,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.connect("activate", self._on_activate)
        self.connect("startup", self._on_startup)

    def _on_startup(self, _app: "LinepipeApp") -> None:
        self._load_css()
        self._apply_saved_scheme()
        self._register_actions()
        self.connect("window-removed", self._on_window_removed)

    def _on_window_removed(self, app: "LinepipeApp", _window: Gtk.Window) -> None:
        if not app.get_windows():
            app.quit()

    def _on_activate(self, _app: "LinepipeApp") -> None:
        win = self.get_active_window()
        if win is None:
            win = MainWindow(application=self)
        win.present()

    # ------------------------------------------------------------------
    # CSS
    # ------------------------------------------------------------------

    def _load_css(self) -> None:
        css_path = self._find_css_path()
        if css_path is None:
            return
        provider = Gtk.CssProvider()
        try:
            provider.load_from_path(str(css_path))
        except Exception:
            return
        Gtk.StyleContext.add_provider_for_display(
            Gtk.Widget.get_display(Gtk.Label()),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _find_css_path(self) -> "Path | None":
        try:
            ref = importlib.resources.files("linepipe").joinpath("style.css")
            if ref.is_file():
                return Path(str(ref))
        except (TypeError, AttributeError):
            pass
        here = Path(__file__).parent
        css = here / "style.css"
        if css.is_file():
            return css
        return None

    # ------------------------------------------------------------------
    # Color scheme
    # ------------------------------------------------------------------

    def _apply_saved_scheme(self) -> None:
        prefs = load_prefs()
        apply_color_scheme(prefs.get("color_scheme", "system"))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _register_actions(self) -> None:
        # Preferences
        prefs_action = Gio.SimpleAction.new("preferences", None)
        prefs_action.connect("activate", self._on_preferences)
        self.add_action(prefs_action)
        self.set_accels_for_action("app.preferences", ["<Control>p"])

        # Shortcuts
        shortcuts_action = Gio.SimpleAction.new("shortcuts", None)
        shortcuts_action.connect("activate", self._on_shortcuts)
        self.add_action(shortcuts_action)
        self.set_accels_for_action("app.shortcuts", ["question"])

        # About
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        # Quit
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])

    def _on_preferences(self, _action, _param) -> None:
        win = self.get_active_window()
        dlg = PreferencesDialog()
        dlg.present(win)

    def _on_shortcuts(self, _action, _param) -> None:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <object class="GtkShortcutsWindow" id="shortcuts_window">
    <property name="modal">1</property>
    <child>
      <object class="GtkShortcutsSection">
        <property name="title">Linepipe</property>
        <child>
          <object class="GtkShortcutsGroup">
            <property name="title">General</property>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title">Refresh</property>
                <property name="accelerator">&lt;Control&gt;r F5</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title">Search</property>
                <property name="accelerator">&lt;Control&gt;f</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title">Install Package</property>
                <property name="accelerator">&lt;Control&gt;i</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title">Preferences</property>
                <property name="accelerator">&lt;Control&gt;p</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title">Keyboard Shortcuts</property>
                <property name="accelerator">question</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="title">Quit</property>
                <property name="accelerator">&lt;Control&gt;q</property>
              </object>
            </child>
          </object>
        </child>
      </object>
    </child>
  </object>
</interface>"""
        builder = Gtk.Builder.new_from_string(xml, -1)
        shortcuts_win = builder.get_object("shortcuts_window")
        if shortcuts_win:
            shortcuts_win.set_transient_for(self.get_active_window())
            shortcuts_win.present()

    def _on_about(self, _action, _param) -> None:
        about = Adw.AboutDialog()
        about.set_application_name("Linepipe")
        about.set_version(__version__)
        about.set_developer_name("Torcken 🤍")
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_comments("A modern GUI for managing pipx packages on Linux")
        about.set_website("https://github.com/Torcken/linepipe")
        about.set_developers(["Torcken 🤍"])
        about.set_copyright("©2025 Made with love 🤍 by Torcken")
        about.set_application_icon(__app_id__)
        about.present(self.get_active_window())


def main() -> int:
    app = LinepipeApp()
    return app.run(sys.argv)
