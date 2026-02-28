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

"""Desktop notification helper for Linepipe."""

from __future__ import annotations

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio


def send_notification(app, title: str, body: str, success: bool = True) -> None:
    """Send a desktop notification via Gio.Application.send_notification()."""
    notification = Gio.Notification.new(title)
    notification.set_body(body)
    icon_name = "dialog-information" if success else "dialog-error"
    icon = Gio.ThemedIcon.new(icon_name)
    notification.set_icon(icon)
    app.send_notification("linepipe-op", notification)
