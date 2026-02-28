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

"""Utility helpers for Linepipe — config I/O and version comparison."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path.home() / ".config" / "linepipe" / "config.json"

_DEFAULTS: dict[str, Any] = {
    "pipx_path": "",
    "color_scheme": "system",
    "include_deps": False,
    "show_prerelease": False,
}


def load_prefs() -> dict[str, Any]:
    """Load config from disk, merging with defaults."""
    prefs = _DEFAULTS.copy()
    if _CONFIG_PATH.is_file():
        try:
            with _CONFIG_PATH.open() as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                prefs.update(data)
        except (json.JSONDecodeError, OSError):
            pass
    return prefs


def save_prefs(prefs: dict[str, Any]) -> None:
    """Persist config to disk."""
    try:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _CONFIG_PATH.open("w") as fh:
            json.dump(prefs, fh, indent=2)
    except OSError:
        pass


def compare_versions(installed: str, latest: str) -> int:
    """Compare version strings. Returns -1, 0, or 1.

    Uses packaging.version if available, falls back to simple tuple comparison.
    """
    try:
        from packaging.version import Version  # type: ignore[import]
        v_inst = Version(installed)
        v_lat = Version(latest)
        if v_inst < v_lat:
            return -1
        if v_inst > v_lat:
            return 1
        return 0
    except Exception:
        pass

    def _to_tuple(v: str) -> tuple[int, ...]:
        parts = []
        for segment in v.split("."):
            try:
                parts.append(int(segment))
            except ValueError:
                parts.append(0)
        return tuple(parts)

    t_inst = _to_tuple(installed)
    t_lat = _to_tuple(latest)
    if t_inst < t_lat:
        return -1
    if t_inst > t_lat:
        return 1
    return 0


def is_outdated(installed: str, latest: str) -> bool:
    """Return True if installed version is older than latest."""
    if not installed or not latest:
        return False
    return compare_versions(installed, latest) < 0
