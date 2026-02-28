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

"""Package list widget — Gtk.ColumnView with virtualised rendering.

Uses Gio.ListStore + Gtk.FilterListModel + Gtk.SortListModel so only
visible rows are rendered.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")
gi.require_version("GObject", "2.0")
from gi.repository import Adw, Gio, GLib, GObject, Gtk


class PackageItem(GObject.GObject):
    """GObject wrapper for a single pipx package entry."""

    __gtype_name__ = "LinepipePackageItem"

    def __init__(
        self,
        name: str = "",
        version: str = "",
        latest_version: str = "",
        python_version: str = "",
        apps: list | None = None,
        injected: list | None = None,
        venv_location: str = "",
        status: str = "installed",
    ) -> None:
        super().__init__()
        self.name = name
        self.version = version
        self.latest_version = latest_version
        self.python_version = python_version
        self.apps: list[str] = apps if apps is not None else []
        self.injected: list[str] = injected if injected is not None else []
        self.venv_location = venv_location
        self.status = status  # "installed" | "outdated" | "unknown"


class PackageListView(Gtk.Box):
    """Filterable, sortable, virtualised package list using Gtk.ColumnView."""

    __gsignals__ = {
        "package-selected": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self._search_text = ""
        self._category = "installed"  # "installed" | "outdated" | "search"

        # Model pipeline: ListStore → FilterListModel → SortListModel → SingleSelection → ColumnView
        self._store = Gio.ListStore(item_type=PackageItem)
        self._filter = Gtk.CustomFilter.new(self._filter_func, None)
        self._filter_model = Gtk.FilterListModel(model=self._store, filter=self._filter)
        self._sorter = Gtk.CustomSorter.new(self._sort_func, None)
        self._sort_model = Gtk.SortListModel(model=self._filter_model, sorter=self._sorter)
        self._selection = Gtk.SingleSelection(model=self._sort_model)
        self._selection.connect("selection-changed", self._on_selection_changed)

        self._column_view = Gtk.ColumnView(model=self._selection)
        self._column_view.set_show_row_separators(True)
        self._column_view.set_show_column_separators(False)
        self._column_view.set_vexpand(True)
        self._column_view.add_css_class("data-table")

        self._build_columns()

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self._column_view)
        self.append(scrolled)

        # Empty state
        self._empty_label = Gtk.Label(label="No packages found")
        self._empty_label.add_css_class("dim-label")
        self._empty_label.set_margin_top(48)
        self._empty_label.set_valign(Gtk.Align.START)

    # ------------------------------------------------------------------
    # Column definitions
    # ------------------------------------------------------------------

    def _build_columns(self) -> None:
        # Name column
        name_factory = Gtk.SignalListItemFactory()
        name_factory.connect("setup", self._setup_name_cell)
        name_factory.connect("bind", self._bind_name_cell)
        name_col = Gtk.ColumnViewColumn(title="Name", factory=name_factory)
        name_col.set_expand(True)
        name_col.set_resizable(True)
        self._column_view.append_column(name_col)

        # Version column
        ver_factory = Gtk.SignalListItemFactory()
        ver_factory.connect("setup", self._setup_version_cell)
        ver_factory.connect("bind", self._bind_version_cell)
        ver_col = Gtk.ColumnViewColumn(title="Version", factory=ver_factory)
        ver_col.set_fixed_width(140)
        self._column_view.append_column(ver_col)

        # Apps column
        apps_factory = Gtk.SignalListItemFactory()
        apps_factory.connect("setup", self._setup_apps_cell)
        apps_factory.connect("bind", self._bind_apps_cell)
        apps_col = Gtk.ColumnViewColumn(title="Apps", factory=apps_factory)
        apps_col.set_fixed_width(70)
        self._column_view.append_column(apps_col)

        # Status column
        status_factory = Gtk.SignalListItemFactory()
        status_factory.connect("setup", self._setup_status_cell)
        status_factory.connect("bind", self._bind_status_cell)
        status_col = Gtk.ColumnViewColumn(title="Status", factory=status_factory)
        status_col.set_fixed_width(110)
        self._column_view.append_column(status_col)

    # ------------------------------------------------------------------
    # Cell setup / bind helpers
    # ------------------------------------------------------------------

    def _setup_name_cell(self, _factory, item: Gtk.ListItem) -> None:
        label = Gtk.Label(xalign=0)
        label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        label.set_margin_start(8)
        label.set_margin_top(6)
        label.set_margin_bottom(6)
        item.set_child(label)

    def _bind_name_cell(self, _factory, item: Gtk.ListItem) -> None:
        pkg: PackageItem = item.get_item()
        label: Gtk.Label = item.get_child()
        label.set_label(pkg.name)

    def _setup_version_cell(self, _factory, item: Gtk.ListItem) -> None:
        label = Gtk.Label(xalign=0)
        label.set_ellipsize(3)
        label.add_css_class("dim-label")
        label.set_margin_top(6)
        label.set_margin_bottom(6)
        item.set_child(label)

    def _bind_version_cell(self, _factory, item: Gtk.ListItem) -> None:
        pkg: PackageItem = item.get_item()
        label: Gtk.Label = item.get_child()
        label.set_label(pkg.version or "—")

    def _setup_apps_cell(self, _factory, item: Gtk.ListItem) -> None:
        label = Gtk.Label(xalign=1)
        label.add_css_class("dim-label")
        label.set_margin_end(8)
        label.set_margin_top(6)
        label.set_margin_bottom(6)
        item.set_child(label)

    def _bind_apps_cell(self, _factory, item: Gtk.ListItem) -> None:
        pkg: PackageItem = item.get_item()
        label: Gtk.Label = item.get_child()
        label.set_label(str(len(pkg.apps)))

    def _setup_status_cell(self, _factory, item: Gtk.ListItem) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, halign=Gtk.Align.CENTER)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        badge = Gtk.Label()
        badge.add_css_class("status-badge")
        box.append(badge)
        item.set_child(box)

    def _bind_status_cell(self, _factory, item: Gtk.ListItem) -> None:
        pkg: PackageItem = item.get_item()
        box: Gtk.Box = item.get_child()
        badge: Gtk.Label = box.get_first_child()

        for cls in ("badge-installed", "badge-outdated", "badge-unknown"):
            badge.remove_css_class(cls)

        if pkg.status == "outdated":
            badge.set_label("Outdated")
            badge.add_css_class("badge-outdated")
        elif pkg.status == "installed":
            badge.set_label("Installed")
            badge.add_css_class("badge-installed")
        else:
            badge.set_label("Unknown")
            badge.add_css_class("badge-unknown")

    # ------------------------------------------------------------------
    # Filtering / sorting
    # ------------------------------------------------------------------

    def _filter_func(self, item: PackageItem, _user_data) -> bool:
        if self._category == "outdated" and item.status != "outdated":
            return False
        if self._search_text:
            return self._search_text.lower() in item.name.lower()
        return True

    def _sort_func(self, a: PackageItem, b: PackageItem, _user_data) -> int:
        if a.name < b.name:
            return -1
        if a.name > b.name:
            return 1
        return 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_packages(self, packages: list[dict]) -> None:
        """Bulk replace the list store."""
        items = [PackageItem(**p) for p in packages]
        self._store.splice(0, self._store.get_n_items(), items)

    def update_package_status(self, name: str, latest_version: str) -> None:
        """Update a single package's latest version and status."""
        from linepipe.utils import is_outdated
        for i in range(self._store.get_n_items()):
            item: PackageItem = self._store.get_item(i)
            if item.name == name:
                item.latest_version = latest_version
                if latest_version:
                    item.status = "outdated" if is_outdated(item.version, latest_version) else "installed"
                else:
                    item.status = "unknown"
                # Notify filter/sort models of change
                self._store.items_changed(i, 1, 1)
                self._filter.changed(Gtk.FilterChange.DIFFERENT)
                break

    def set_search(self, text: str) -> None:
        self._search_text = text
        self._filter.changed(Gtk.FilterChange.DIFFERENT)

    def set_category(self, category: str) -> None:
        self._category = category
        self._filter.changed(Gtk.FilterChange.DIFFERENT)
        # Clear selection
        self._selection.set_selected(Gtk.INVALID_LIST_POSITION)

    def get_selected_package(self) -> PackageItem | None:
        item = self._selection.get_selected_item()
        return item if isinstance(item, PackageItem) else None

    def get_all_packages(self) -> list[PackageItem]:
        result = []
        for i in range(self._store.get_n_items()):
            result.append(self._store.get_item(i))
        return result

    def get_outdated_count(self) -> int:
        count = 0
        for i in range(self._store.get_n_items()):
            item: PackageItem = self._store.get_item(i)
            if item.status == "outdated":
                count += 1
        return count

    def clear(self) -> None:
        self._store.remove_all()

    # ------------------------------------------------------------------
    # Internal signals
    # ------------------------------------------------------------------

    def _on_selection_changed(self, selection: Gtk.SingleSelection, _pos: int, _n: int) -> None:
        item = selection.get_selected_item()
        self.emit("package-selected", item)
