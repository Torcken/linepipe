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

"""PyPI Simple Index — local SQLite cache + fast in-memory search.

Two datasets, both cached in the same SQLite DB:

  top_packages  — ranked list of the most-downloaded packages, fetched from
                  hugovk.github.io/top-pypi-packages. Fetched automatically on
                  first run; used as the default "Search PyPI" view.

  packages      — full PyPI simple index (~600 k names). Synced manually via
                  "Sync Package Index". Used for comprehensive typed search.

Flow:
  1. Startup: load_top_into_memory() + load_into_memory() read from SQLite.
  2. If top packages absent: fetch_top_packages() downloads them silently.
  3. "Search PyPI" initial view shows top packages (ranked by downloads).
  4. User types → search_top() if only top loaded, search() if full index ready.
  5. "Sync Package Index" fetches/refreshes the full 600 k list.

SQLite path: ~/.cache/linepipe/pypi_index.db
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib

_CACHE_DIR = Path.home() / ".cache" / "linepipe"
_DB_PATH = _CACHE_DIR / "pypi_index.db"
_SIMPLE_URL = "https://pypi.org/simple/"
_SIMPLE_ACCEPT = "application/vnd.pypi.simple.v1+json"
_USER_AGENT = "Linepipe/1.0 (https://github.com/Torcken/linepipe)"
# Top-packages dataset: top ~8 000 PyPI packages ranked by 30-day downloads
_TOP_URL = "https://hugovk.github.io/top-pypi-packages/top-pypi-packages-30-days.min.json"

# ---------------------------------------------------------------------------
# In-memory indices (loaded once from SQLite, rebuilt after every sync/fetch)
# ---------------------------------------------------------------------------

_names: list[str] = []        # full index — original-case names
_norms: list[str] = []        # full index — normalized (lowercase, _ → -)
_top_names: list[str] = []    # top packages — original-case, ordered by rank
_top_norms: list[str] = []    # top packages — normalized, ordered by rank
_index_lock = threading.Lock()


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def _open_db() -> sqlite3.Connection:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS packages "
        "(name TEXT PRIMARY KEY, norm TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS top_packages "
        "(rank INTEGER PRIMARY KEY, name TEXT NOT NULL, norm TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Public: stats
# ---------------------------------------------------------------------------

def get_stats() -> dict:
    """Return {'count': int, 'last_updated': str|None} from the local cache."""
    try:
        conn = _open_db()
        count = conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0]
        row = conn.execute(
            "SELECT value FROM meta WHERE key='last_updated'"
        ).fetchone()
        conn.close()
        return {"count": count, "last_updated": row[0] if row else None}
    except Exception:
        return {"count": 0, "last_updated": None}


def get_memory_count() -> int:
    """Return number of full-index names in memory (0 if not synced yet)."""
    with _index_lock:
        return len(_names)


def is_loaded() -> bool:
    """Return True if the full in-memory index has been populated."""
    with _index_lock:
        return bool(_names)


def get_top_count() -> int:
    """Return number of top-packages names currently in memory."""
    with _index_lock:
        return len(_top_names)


def has_top_packages() -> bool:
    """Return True if the top-packages list is loaded in memory."""
    with _index_lock:
        return bool(_top_names)


def get_top_packages() -> list[str]:
    """Return the in-memory top-packages list (ordered by rank/popularity)."""
    with _index_lock:
        return list(_top_names)


# ---------------------------------------------------------------------------
# Public: load top packages into memory (async, call once at startup)
# ---------------------------------------------------------------------------

def load_top_into_memory(
    callback: Optional[Callable[[int], None]] = None,
) -> None:
    """Load top-packages names from SQLite into memory (daemon thread).

    callback(count) is called on the GTK main thread when done.
    count == 0 means the table is empty → caller should trigger a fetch.
    """
    def _worker() -> None:
        global _top_names, _top_norms
        try:
            conn = _open_db()
            rows = conn.execute(
                "SELECT name, norm FROM top_packages ORDER BY rank"
            ).fetchall()
            conn.close()
            names = [r[0] for r in rows]
            norms = [r[1] for r in rows]
        except Exception:
            names, norms = [], []

        with _index_lock:
            _top_names = names
            _top_norms = norms

        if callback:
            GLib.idle_add(callback, len(names))

    threading.Thread(target=_worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Public: fetch top packages (async, ProgressDialog-compatible)
# ---------------------------------------------------------------------------

def fetch_top_packages(
    on_line: Optional[Callable[[str], None]] = None,
    on_complete: Optional[Callable[[int, str], None]] = None,
) -> None:
    """Download the top-packages ranked list and cache it in SQLite.

    Source: hugovk.github.io/top-pypi-packages (30-day download stats).
    Signature is ProgressDialog-compatible (same as sync / run_pipx_async).
    """

    def _emit(line: str) -> None:
        if on_line:
            GLib.idle_add(on_line, line)

    def _done(rc: int, msg: str) -> None:
        if on_complete:
            GLib.idle_add(on_complete, rc, msg)

    def _worker() -> None:
        global _top_names, _top_norms
        try:
            _emit("Fetching top PyPI packages list…\n")
            req = urllib.request.Request(
                _TOP_URL, headers={"User-Agent": _USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", errors="replace")

            _emit("Parsing rankings…\n")
            data = json.loads(raw)
            rows = data.get("rows", [])
            count = len(rows)

            _emit(f"Storing {count:,} packages…\n")
            conn = _open_db()
            conn.execute("DELETE FROM top_packages")
            conn.executemany(
                "INSERT INTO top_packages (rank, name, norm) VALUES (?, ?, ?)",
                [
                    (i + 1, r["project"], r["project"].lower().replace("_", "-"))
                    for i, r in enumerate(rows)
                ],
            )
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO meta VALUES ('top_last_updated', ?)",
                (now,),
            )
            conn.commit()
            conn.close()

            names = [r["project"] for r in rows]
            norms = [r["project"].lower().replace("_", "-") for r in rows]
            with _index_lock:
                _top_names = names
                _top_norms = norms

            msg = f"Top {count:,} packages loaded.\n"
            _emit(msg)
            _done(0, msg)

        except urllib.error.URLError as exc:
            msg = f"Network error: {exc.reason}\n"
            _emit(msg)
            _done(1, msg)
        except Exception as exc:
            msg = f"Failed to fetch top packages: {exc}\n"
            _emit(msg)
            _done(1, msg)

    threading.Thread(target=_worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Public: search top packages only (for when full index is not loaded)
# ---------------------------------------------------------------------------

def search_top(query: str, limit: int = 300) -> list[str]:
    """Substring search within the top-packages list.

    Preserves rank order: results that match the prefix come first.
    Safe to call from a background thread.
    """
    if not query:
        return []

    q = query.lower().replace("_", "-")

    with _index_lock:
        names_snap = _top_names
        norms_snap = _top_norms

    if not names_snap:
        return []

    prefix: list[str] = []
    other: list[str] = []

    for name, norm in zip(names_snap, norms_snap):
        if q not in norm:
            continue
        if norm.startswith(q):
            prefix.append(name)
        else:
            other.append(name)
        if len(prefix) + len(other) >= limit * 2:
            break

    return (prefix + other)[:limit]


# ---------------------------------------------------------------------------
# Public: load into memory (async, call once at startup)
# ---------------------------------------------------------------------------

def load_into_memory(callback: Optional[Callable[[int], None]] = None) -> None:
    """Load all package names from SQLite into memory (daemon thread).

    callback(count) is called on the GTK main thread when done.
    """
    def _worker() -> None:
        global _names, _norms
        try:
            conn = _open_db()
            rows = conn.execute(
                "SELECT name, norm FROM packages ORDER BY norm"
            ).fetchall()
            conn.close()
            names = [r[0] for r in rows]
            norms = [r[1] for r in rows]
        except Exception:
            names, norms = [], []

        with _index_lock:
            _names = names
            _norms = norms

        if callback:
            GLib.idle_add(callback, len(names))

    threading.Thread(target=_worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Public: search (synchronous, safe to call from a background thread)
# ---------------------------------------------------------------------------

def search(query: str, limit: int = 300) -> list[str]:
    """Return up to `limit` package names whose normalized name contains `query`.

    Call from a background thread — iterating 600k strings may take ~100-200ms.
    Results are sorted: prefix matches first, then other substring matches.
    """
    if not query:
        return []

    q = query.lower().replace("_", "-")

    with _index_lock:
        names_snap = _names
        norms_snap = _norms

    if not names_snap:
        return []

    prefix: list[str] = []
    other: list[str] = []

    for name, norm in zip(names_snap, norms_snap):
        if q not in norm:
            continue
        if norm.startswith(q):
            prefix.append(name)
        else:
            other.append(name)
        if len(prefix) + len(other) >= limit * 2:
            break

    result = prefix + other
    return result[:limit]


# ---------------------------------------------------------------------------
# Public: sync (async, ProgressDialog-compatible signature)
# ---------------------------------------------------------------------------

def sync(
    on_line: Optional[Callable[[str], None]] = None,
    on_complete: Optional[Callable[[int, str], None]] = None,
) -> None:
    """Download (or conditionally refresh) the PyPI Simple index.

    Signature matches run_pipx_async — compatible with ProgressDialog.
    Progress messages are emitted via on_line(); on_complete(rc, msg) on finish.
    All callbacks are dispatched via GLib.idle_add().
    """

    def _emit(line: str) -> None:
        if on_line:
            GLib.idle_add(on_line, line)

    def _done(rc: int, msg: str) -> None:
        if on_complete:
            GLib.idle_add(on_complete, rc, msg)

    def _worker() -> None:
        global _names, _norms
        try:
            conn = _open_db()
            row = conn.execute(
                "SELECT value FROM meta WHERE key='etag'"
            ).fetchone()
            etag: Optional[str] = row[0] if row else None

            headers: dict[str, str] = {
                "Accept": _SIMPLE_ACCEPT,
                "User-Agent": _USER_AGENT,
            }
            if etag:
                headers["If-None-Match"] = etag

            req = urllib.request.Request(_SIMPLE_URL, headers=headers)
            _emit("Connecting to PyPI index…\n")

            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    new_etag = resp.headers.get("ETag", "")
                    _emit("Downloading package list… (this may take a moment)\n")
                    raw = resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                if exc.code == 304:
                    conn.close()
                    _emit("Index is already up to date.\n")
                    _done(0, "Index is already up to date.")
                    return
                raise

            _emit("Parsing package list…\n")
            data = json.loads(raw)
            projects = data.get("projects", [])
            count = len(projects)
            _emit(f"Storing {count:,} packages in local cache…\n")

            conn.execute("DELETE FROM packages")
            conn.executemany(
                "INSERT INTO packages (name, norm) VALUES (?, ?)",
                [(p["name"], p["name"].lower().replace("_", "-")) for p in projects],
            )

            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO meta VALUES ('last_updated', ?)", (now,)
            )
            if new_etag:
                conn.execute(
                    "INSERT OR REPLACE INTO meta VALUES ('etag', ?)", (new_etag,)
                )
            conn.commit()
            conn.close()

            # Rebuild in-memory index
            names = [p["name"] for p in projects]
            norms = [p["name"].lower().replace("_", "-") for p in projects]
            with _index_lock:
                _names = names
                _norms = norms

            msg = f"Index updated: {count:,} packages indexed.\n"
            _emit(msg)
            _done(0, msg)

        except urllib.error.URLError as exc:
            msg = f"Network error: {exc.reason}\n"
            _emit(msg)
            _done(1, msg)
        except Exception as exc:
            msg = f"Sync failed: {exc}\n"
            _emit(msg)
            _done(1, msg)

    threading.Thread(target=_worker, daemon=True).start()
