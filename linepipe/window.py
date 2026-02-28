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

"""Main window — three-pane layout: sidebar | package list | detail pane."""

from __future__ import annotations

from typing import Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Adw, Gio, GLib, Gtk

from linepipe import __app_id__
from linepipe.detail_panel import DetailPanel
from linepipe.dialogs import InjectDialog, InstallDialog, RunDialog
from linepipe.package_list import PackageItem, PackageListView
from linepipe.progress_dialog import ProgressDialog
import linepipe.pipx_interface as pipx
from linepipe.pipx_interface import FEATURED_PACKAGES
from linepipe.notifications import send_notification


_CATEGORIES = [
    {"id": "installed", "label": "Installed", "icon": "drive-harddisk-symbolic"},
    {"id": "outdated",  "label": "Outdated",  "icon": "software-update-available-symbolic"},
    {"id": "search",    "label": "Search PyPI","icon": "system-search-symbolic"},
]


class MainWindow(Adw.ApplicationWindow):
    """Three-pane layout: sidebar | package list | detail pane."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Linepipe")
        self.set_default_size(1100, 680)
        self.set_icon_name(__app_id__)

        self._current_category = "installed"
        self._packages: list[dict] = []
        self._pypi_result: Optional[dict] = None

        self._build_ui()
        self._register_window_actions()

        GLib.idle_add(self._refresh_packages)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Toast overlay wraps everything
        self._toast_overlay = Adw.ToastOverlay()

        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Banner for missing pipx
        self._banner = Adw.Banner()
        self._banner.set_title("pipx not found. Install it to use Linepipe.")
        self._banner.set_button_label("Get pipx")
        self._banner.connect("button-clicked", self._on_banner_clicked)
        self._banner.set_revealed(False)
        outer_box.append(self._banner)

        # Overlay paned layout
        paned_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        paned_box.set_vexpand(True)

        # Top: headerbar
        self._header = Adw.HeaderBar()
        self._build_header(self._header)
        paned_box.append(self._header)

        # Search bar (below header)
        self._search_bar = Gtk.SearchBar()
        self._search_bar.set_show_close_button(True)

        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text("Filter installed… type a name + press Enter or click Search PyPI")
        self._search_entry.set_hexpand(True)
        self._search_entry.connect("search-changed", self._on_search_changed)
        self._search_entry.connect("activate", self._on_search_activate)
        search_box.append(self._search_entry)

        self._pypi_btn = Gtk.Button(label="Search PyPI")
        self._pypi_btn.set_icon_name("system-search-symbolic")
        self._pypi_btn.set_tooltip_text("Look up this package name on PyPI")
        self._pypi_btn.connect("clicked", lambda _: self._on_search_activate(self._search_entry))
        search_box.append(self._pypi_btn)

        self._search_bar.set_child(search_box)
        self._search_bar.set_key_capture_widget(self)
        paned_box.append(self._search_bar)

        # Main area: sidebar + list + detail
        main_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        main_paned.set_vexpand(True)
        main_paned.set_position(200)

        # Sidebar
        sidebar = self._build_sidebar()
        main_paned.set_start_child(sidebar)
        main_paned.set_shrink_start_child(False)
        main_paned.set_resize_start_child(False)

        # Right: list + detail
        right_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        right_paned.set_vexpand(True)
        right_paned.set_position(520)

        self._package_list_view = PackageListView()
        self._package_list_view.connect("package-selected", self._on_package_selected)
        right_paned.set_start_child(self._package_list_view)
        right_paned.set_shrink_start_child(False)

        self._detail_panel = DetailPanel()
        self._detail_panel.connect("install-requested",   self._on_install_from_detail)
        self._detail_panel.connect("uninstall-requested", self._on_uninstall_from_detail)
        self._detail_panel.connect("upgrade-requested",   self._on_upgrade_from_detail)
        self._detail_panel.connect("inject-requested",    self._on_inject_from_detail)
        self._detail_panel.connect("run-requested",       self._on_run_from_detail)
        right_paned.set_end_child(self._detail_panel)
        right_paned.set_shrink_end_child(False)

        main_paned.set_end_child(right_paned)

        paned_box.append(main_paned)
        outer_box.append(paned_box)

        self._toast_overlay.set_child(outer_box)
        self.set_content(self._toast_overlay)

        # Select first category
        first_row = self._category_list.get_row_at_index(0)
        self._category_list.select_row(first_row)

    def _build_header(self, header: Adw.HeaderBar) -> None:
        # Search toggle
        self._search_toggle = Gtk.ToggleButton()
        self._search_toggle.set_icon_name("system-search-symbolic")
        self._search_toggle.set_tooltip_text("Search (Ctrl+F)")
        self._search_toggle.connect("toggled", self._on_search_toggled)
        header.pack_end(self._search_toggle)

        # Refresh
        refresh_btn = Gtk.Button()
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh (Ctrl+R / F5)")
        refresh_btn.connect("clicked", lambda _: self._refresh_packages())
        header.pack_end(refresh_btn)

        # Menu
        menu_model = Gio.Menu()
        # Package operations section
        pkg_section = Gio.Menu()
        pkg_section.append("Install Package…",  "win.install")
        pkg_section.append("Upgrade All",        "win.upgrade-all")
        pkg_section.append("Reinstall All",      "win.reinstall-all")
        pkg_section.append("Check for Updates",  "win.check-updates")
        menu_model.append_section(None, pkg_section)

        # App section
        app_section = Gio.Menu()
        app_section.append("Preferences",       "app.preferences")
        app_section.append("Keyboard Shortcuts", "app.shortcuts")
        app_section.append("About Linepipe",     "app.about")
        menu_model.append_section(None, app_section)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_menu_model(menu_model)
        header.pack_start(menu_btn)

    def _build_sidebar(self) -> Gtk.Widget:
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.set_size_request(180, -1)

        self._category_list = Gtk.ListBox()
        self._category_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._category_list.add_css_class("navigation-sidebar")
        self._category_list.connect("row-selected", self._on_category_selected)
        self._category_list.set_vexpand(True)

        self._count_labels: dict[str, Gtk.Label] = {}

        for cat in _CATEGORIES:
            row = self._build_category_row(cat)
            self._category_list.append(row)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self._category_list)
        sidebar_box.append(scrolled)

        return sidebar_box

    def _build_category_row(self, cat: dict) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row._cat_id = cat["id"]  # type: ignore[attr-defined]

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        icon = Gtk.Image.new_from_icon_name(cat["icon"])
        icon.set_pixel_size(16)
        box.append(icon)

        label = Gtk.Label(label=cat["label"])
        label.set_xalign(0)
        label.set_hexpand(True)
        box.append(label)

        count_lbl = Gtk.Label(label="")
        count_lbl.add_css_class("dim-label")
        count_lbl.add_css_class("caption")
        self._count_labels[cat["id"]] = count_lbl
        box.append(count_lbl)

        row.set_child(box)
        return row

    # ------------------------------------------------------------------
    # Window actions
    # ------------------------------------------------------------------

    def _register_window_actions(self) -> None:
        actions = [
            ("install",        lambda *_: self._open_install_dialog()),
            ("upgrade-all",    lambda *_: self._run_upgrade_all()),
            ("reinstall-all",  lambda *_: self._run_reinstall_all()),
            ("check-updates",  lambda *_: self._run_check_for_updates()),
            ("refresh",        lambda *_: self._refresh_packages()),
            ("focus-search",   lambda *_: self._focus_search()),
        ]
        for name, cb in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            self.add_action(action)

        app = self.get_application()
        if app:
            app.set_accels_for_action("win.refresh",      ["<Control>r", "F5"])
            app.set_accels_for_action("win.install",      ["<Control>i"])
            app.set_accels_for_action("win.focus-search", ["<Control>f"])

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _refresh_packages(self) -> None:
        if pipx.find_pipx() is None:
            self._banner.set_revealed(True)
            return
        self._banner.set_revealed(False)
        pipx.get_installed_packages(self._on_packages_loaded)

    def _featured_packages(self) -> list[dict]:
        """Return FEATURED_PACKAGES, marking already-installed ones."""
        installed_names = {p["name"] for p in self._packages}
        result = []
        for pkg in FEATURED_PACKAGES:
            entry = dict(pkg)
            if entry["name"] in installed_names:
                entry["status"] = "installed"
            result.append(entry)
        return result

    def _on_packages_loaded(self, packages: list[dict]) -> None:
        self._packages = packages
        # Only push to the list view if not in search/featured mode
        if self._current_category != "search":
            self._package_list_view.set_packages(packages)
        self._update_category_counts()
        self._detail_panel.show_empty()

        from linepipe.utils import load_prefs
        prefs = load_prefs()
        pipx.check_pypi_versions(
            packages,
            self._on_pypi_version_result,
            show_prerelease=prefs.get("show_prerelease", False),
        )

    def _on_pypi_version_result(self, name: str, latest_version: str) -> None:
        self._package_list_view.update_package_status(name, latest_version)
        self._update_category_counts()

        # Refresh detail if this package is shown
        if (
            self._detail_panel.current_name == name
            and not self._detail_panel._is_pypi_result
        ):
            pkg = self._package_list_view.get_selected_package()
            if pkg and pkg.name == name:
                self._detail_panel.show_package(pkg)

    def _update_category_counts(self) -> None:
        total = len(self._packages)
        outdated = self._package_list_view.get_outdated_count()
        self._count_labels["installed"].set_label(str(total) if total else "")
        self._count_labels["outdated"].set_label(str(outdated) if outdated else "")
        self._count_labels["search"].set_label("")

    # ------------------------------------------------------------------
    # Category selection
    # ------------------------------------------------------------------

    def _on_category_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        if row is None:
            return
        cat_id = getattr(row, "_cat_id", "installed")
        self._current_category = cat_id

        if cat_id == "search":
            self._package_list_view.set_packages(self._featured_packages())
            self._package_list_view.set_category("available")
            self._search_toggle.set_active(True)
            self._detail_panel.show_search_hint()
            GLib.idle_add(self._search_entry.grab_focus)
        else:
            # Restore installed packages when leaving search
            self._package_list_view.set_packages(self._packages)
            self._package_list_view.set_category(cat_id)
            self._detail_panel.show_empty()

        self._pypi_result = None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search_toggled(self, btn: Gtk.ToggleButton) -> None:
        active = btn.get_active()
        self._search_bar.set_search_mode(active)
        if active:
            self._search_entry.grab_focus()
        else:
            self._search_entry.set_text("")
            self._package_list_view.set_search("")

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        text = entry.get_text().strip()
        self._package_list_view.set_search(text)
        if not text:
            self._pypi_result = None

    def _on_search_activate(self, entry: Gtk.SearchEntry) -> None:
        """On Enter: perform exact PyPI package lookup."""
        name = entry.get_text().strip()
        if not name:
            return
        self._detail_panel.show_loading(name)
        pipx.query_pypi(name, self._on_pypi_result)

    def _on_pypi_result(self, info: Optional[dict]) -> None:
        if info is None:
            self._detail_panel.show_empty()
            self._show_toast("Package not found on PyPI.")
            return
        self._pypi_result = info
        self._detail_panel.show_package(info, is_pypi_result=True)

    def _focus_search(self) -> None:
        self._search_toggle.set_active(True)
        self._search_entry.grab_focus()

    # ------------------------------------------------------------------
    # Package selection
    # ------------------------------------------------------------------

    def _on_package_selected(self, _widget, item) -> None:
        if item is None:
            self._detail_panel.show_empty()
            return
        if item.status == "available":
            # Featured package — query PyPI for full details
            self._detail_panel.show_loading(item.name)
            pipx.query_pypi(item.name, self._on_pypi_result)
        else:
            self._detail_panel.show_package(item, is_pypi_result=False)

    # ------------------------------------------------------------------
    # Detail panel callbacks
    # ------------------------------------------------------------------

    def _on_install_from_detail(self, _panel, name: str) -> None:
        self._open_install_dialog(initial_name=name)

    def _on_uninstall_from_detail(self, _panel, name: str) -> None:
        self._confirm_destructive(
            heading=f"Uninstall '{name}'?",
            body=f"This will remove '{name}' and all its apps from your system.",
            confirm_label="Uninstall",
            on_confirm=lambda: self._run_operation(
                f"Uninstalling {name}",
                lambda ol, oc: pipx.uninstall_package(name, ol, oc),
                success_msg=f"'{name}' was uninstalled.",
                error_msg=f"Failed to uninstall '{name}'.",
            ),
        )

    def _on_upgrade_from_detail(self, _panel, name: str) -> None:
        self._run_operation(
            f"Upgrading {name}",
            lambda ol, oc: pipx.upgrade_package(name, ol, oc),
            success_msg=f"'{name}' was upgraded.",
            error_msg=f"Failed to upgrade '{name}'.",
        )

    def _on_inject_from_detail(self, _panel, name: str) -> None:
        def _do_inject(deps: list[str]) -> None:
            self._run_operation(
                f"Injecting into {name}",
                lambda ol, oc: pipx.inject_packages(name, deps, ol, oc),
                success_msg=f"Dependencies injected into '{name}'.",
                error_msg=f"Failed to inject into '{name}'.",
            )
        InjectDialog(self, pkg_name=name, on_inject=_do_inject).present(self)

    def _on_run_from_detail(self, _panel, name: str) -> None:
        pkg = self._package_list_view.get_selected_package()
        apps = pkg.apps if pkg and pkg.name == name else [name]

        def _do_run(app_name: str, extra_args: list[str]) -> None:
            self._run_operation(
                f"Running {app_name}",
                lambda ol, oc: pipx.run_app(app_name, extra_args, ol, oc),
                success_msg=f"'{app_name}' exited.",
                error_msg=f"'{app_name}' exited with an error.",
                refresh=False,
            )
        RunDialog(self, pkg_name=name, apps=apps, on_run=_do_run).present(self)

    # ------------------------------------------------------------------
    # Install dialog
    # ------------------------------------------------------------------

    def _open_install_dialog(self, initial_name: str = "") -> None:
        InstallDialog(
            self,
            on_install=self._do_install,
            initial_name=initial_name,
        ).present(self)

    def _do_install(self, name: str, ver_spec: str, include_deps: bool, python_path: str) -> None:
        self._run_operation(
            f"Installing {name}",
            lambda ol, oc: pipx.install_package(name, ver_spec, include_deps, python_path, ol, oc),
            success_msg=f"'{name}' was installed.",
            error_msg=f"Failed to install '{name}'.",
        )

    # ------------------------------------------------------------------
    # Upgrade / reinstall all
    # ------------------------------------------------------------------

    def _run_upgrade_all(self) -> None:
        self._run_operation(
            "Upgrading All Packages",
            lambda ol, oc: pipx.upgrade_all_packages(ol, oc),
            success_msg="All packages upgraded.",
            error_msg="Upgrade-all encountered errors.",
        )

    def _run_check_for_updates(self) -> None:
        pkgs = self._package_list_view.get_all_packages()
        if not pkgs:
            self._show_toast("No packages installed to check.")
            return
        from linepipe.utils import load_prefs
        prefs = load_prefs()
        pkg_dicts = [{"name": p.name, "version": p.version} for p in pkgs]
        self._show_toast("Checking for updates…")
        pipx.check_pypi_versions(
            pkg_dicts,
            self._on_pypi_version_result,
            show_prerelease=prefs.get("show_prerelease", False),
        )

    def _run_reinstall_all(self) -> None:
        self._run_operation(
            "Reinstalling All Packages",
            lambda ol, oc: pipx.reinstall_all(ol, oc),
            success_msg="All packages reinstalled.",
            error_msg="Reinstall-all encountered errors.",
        )

    # ------------------------------------------------------------------
    # Generic operation runner
    # ------------------------------------------------------------------

    def _run_operation(
        self,
        title: str,
        start_fn,
        success_msg: str = "Done.",
        error_msg: str = "Operation failed.",
        refresh: bool = True,
    ) -> None:
        app = self.get_application()

        def on_done(returncode: int, _output: str) -> None:
            if returncode == 0:
                self._show_toast(success_msg)
                if app:
                    send_notification(app, "Linepipe", success_msg, success=True)
                if refresh:
                    self._refresh_packages()
            else:
                self._show_toast(error_msg)
                if app:
                    send_notification(app, "Linepipe", error_msg, success=False)

        ProgressDialog(parent=self, title=title, start_fn=start_fn, on_done=on_done)

    # ------------------------------------------------------------------
    # Confirmation dialog
    # ------------------------------------------------------------------

    def _confirm_destructive(
        self,
        heading: str,
        body: str,
        confirm_label: str,
        on_confirm,
    ) -> None:
        dialog = Adw.AlertDialog()
        dialog.set_heading(heading)
        dialog.set_body(body)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("confirm", confirm_label)
        dialog.set_response_appearance("confirm", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda dlg, resp: on_confirm() if resp == "confirm" else None)
        dialog.present(self)

    # ------------------------------------------------------------------
    # Toast
    # ------------------------------------------------------------------

    def _show_toast(self, message: str) -> None:
        toast = Adw.Toast.new(message)
        toast.set_timeout(3)
        self._toast_overlay.add_toast(toast)

    # ------------------------------------------------------------------
    # Banner
    # ------------------------------------------------------------------

    def _on_banner_clicked(self, _banner: Adw.Banner) -> None:
        import subprocess
        try:
            subprocess.Popen(
                ["xdg-open", "https://pipx.pypa.io/"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass
