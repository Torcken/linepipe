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

"""Progress dialog — modal window streaming pipx command output in real-time."""

from __future__ import annotations

from typing import Callable, Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")
from gi.repository import Adw, GLib, Gtk


class ProgressDialog(Gtk.Window):
    """Modal window that streams command output with a pulsing progress bar.

    Constructor takes start_fn(on_line, on_complete) which kicks off the
    subprocess. Dialog shows pulsing progress bar, colour-coded terminal
    output, and a Close button enabled after completion.
    """

    def __init__(
        self,
        parent: Gtk.Window,
        title: str,
        start_fn: Callable[[Callable[[str], None], Callable[[int, str], None]], None],
        on_done: Optional[Callable[[int, str], None]] = None,
    ) -> None:
        super().__init__()
        self.set_title(title)
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(600, 420)
        self.set_resizable(True)

        self._on_done = on_done
        self._returncode: Optional[int] = None
        self._full_output = ""
        self._pulse_id: Optional[int] = None

        # Layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Header bar
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(False)
        main_box.append(header)

        # Content
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(16)

        # Progress bar
        self._progress = Gtk.ProgressBar()
        self._progress.set_pulse_step(0.05)
        content.append(self._progress)

        # Terminal output
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hscrollbar_policy(Gtk.PolicyType.AUTOMATIC)

        self._text_view = Gtk.TextView()
        self._text_view.set_editable(False)
        self._text_view.set_cursor_visible(False)
        self._text_view.set_monospace(True)
        self._text_view.add_css_class("terminal-view")
        self._text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

        self._buffer = self._text_view.get_buffer()
        self._setup_text_tags()

        scrolled.set_child(self._text_view)
        content.append(scrolled)

        # Close button
        self._close_btn = Gtk.Button(label="Close")
        self._close_btn.set_sensitive(False)
        self._close_btn.set_halign(Gtk.Align.END)
        self._close_btn.connect("clicked", lambda _: self.close())
        content.append(self._close_btn)

        main_box.append(content)
        self.set_child(main_box)

        # Start pulsing and run the command
        self._pulse_id = GLib.timeout_add(80, self._pulse)
        start_fn(self._on_line, self._on_complete)

        self.present()

    def _setup_text_tags(self) -> None:
        tag_table = self._buffer.get_tag_table()

        header_tag = Gtk.TextTag(name="header")
        header_tag.set_property("foreground", "#89b4fa")
        tag_table.add(header_tag)

        error_tag = Gtk.TextTag(name="error")
        error_tag.set_property("foreground", "#f38ba8")
        tag_table.add(error_tag)

        success_tag = Gtk.TextTag(name="success")
        success_tag.set_property("foreground", "#a6e3a1")
        tag_table.add(success_tag)

        warning_tag = Gtk.TextTag(name="warning")
        warning_tag.set_property("foreground", "#f9e2af")
        tag_table.add(warning_tag)

    def _pulse(self) -> bool:
        if self._returncode is None:
            self._progress.pulse()
            return True
        return False

    def _on_line(self, line: str) -> None:
        tag_name: Optional[str] = None
        lower = line.lower()

        if any(kw in lower for kw in ("error:", "failed", "traceback", "exception")):
            tag_name = "error"
        elif any(kw in lower for kw in ("warning:", "warn:")):
            tag_name = "warning"
        elif any(kw in lower for kw in ("successfully", "installed", "upgraded", "done")):
            tag_name = "success"
        elif line.startswith("  ") or line.startswith("="):
            tag_name = "header"

        end_iter = self._buffer.get_end_iter()
        if tag_name:
            self._buffer.insert_with_tags_by_name(end_iter, line, tag_name)
        else:
            self._buffer.insert(end_iter, line)

        # Auto-scroll to bottom
        adj = self._text_view.get_parent().get_vadjustment()
        adj.set_value(adj.get_upper())

    def _on_complete(self, returncode: int, full_output: str) -> None:
        self._returncode = returncode
        self._full_output = full_output

        # Stop pulsing
        if self._pulse_id is not None:
            GLib.source_remove(self._pulse_id)
            self._pulse_id = None

        # Set progress bar to full or error state
        if returncode == 0:
            self._progress.set_fraction(1.0)
            self._append_status_line("\n✓ Completed successfully\n", "success")
        else:
            self._progress.set_fraction(1.0)
            self._append_status_line(f"\n✗ Exited with code {returncode}\n", "error")

        self._close_btn.set_sensitive(True)
        self._close_btn.grab_focus()

        if self._on_done:
            self._on_done(returncode, full_output)

    def _append_status_line(self, text: str, tag_name: str) -> None:
        end_iter = self._buffer.get_end_iter()
        self._buffer.insert_with_tags_by_name(end_iter, text, tag_name)
        adj = self._text_view.get_parent().get_vadjustment()
        adj.set_value(adj.get_upper())
