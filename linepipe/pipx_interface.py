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

"""pipx CLI interface — all subprocess wrappers for Linepipe.

All public async functions accept:
  on_line(str)  — called for each output line (dispatched via GLib.idle_add)
  on_complete(returncode: int, full_output: str)  — called on finish

Sync helpers are for background data-fetch threads only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import urllib.request
import urllib.error
from typing import Callable, Optional

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib

from linepipe.utils import load_prefs

_pipx_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Curated list of popular pipx-installable tools
# ---------------------------------------------------------------------------

def _pkg(name: str) -> dict:
    return {
        "name": name, "version": "", "status": "available", "apps": [],
        "injected": [], "python_version": "", "venv_location": "", "latest_version": "",
    }


FEATURED_PACKAGES: list[dict] = [_pkg(n) for n in [
    # ── Code Quality & Linting ────────────────────────────────────────────
    "black", "ruff", "mypy", "pylint", "isort", "bandit", "flake8",
    "autopep8", "pycodestyle", "pydocstyle", "vulture", "radon", "xenon",
    "prospector", "pyright", "semgrep", "dodgy", "safety", "pip-audit",
    "creosote", "deptry", "refurb", "shed", "autoflake", "pyupgrade",
    "ssort", "unimport", "tryceratops", "basedpyright", "ruff-lsp",
    "dlint", "wemake-python-styleguide", "pylama", "eradicate",
    "flake8-bugbear", "flake8-docstrings", "astpretty",
    "pylsp-mypy", "python-lsp-server", "deadcode",
    # ── Type Checking ─────────────────────────────────────────────────────
    "pyre-check", "pyrefly",
    # ── Testing ───────────────────────────────────────────────────────────
    "pytest", "nox", "tox", "coverage", "hypothesis", "mutmut", "ward",
    "behave", "robotframework", "tavern", "pytest-cov", "pytest-xdist",
    "pytest-mock", "pytest-asyncio", "faker", "factory-boy", "responses",
    "freezegun", "time-machine", "pyfakefs", "locust", "molotov",
    "pytest-benchmark", "pytest-randomly", "pytest-sugar", "pytest-timeout",
    "pytest-repeat", "nose2", "green", "pytest-html", "allure-pytest",
    "schemathesis", "pact-python", "vcrpy", "httpretty", "respx",
    # ── Build & Packaging ─────────────────────────────────────────────────
    "poetry", "pdm", "hatch", "pipenv", "build", "twine", "flit", "uv",
    "bumpversion", "bump2version", "tbump", "check-wheel-contents",
    "check-manifest", "pyroma", "auditwheel", "pip-tools", "pipdeptree",
    "pip-check", "johnnydepps", "cibuildwheel", "setuptools-scm",
    "wheel", "installer", "pep517", "python-semantic-release",
    # ── Documentation ─────────────────────────────────────────────────────
    "mkdocs", "sphinx", "pdoc", "pydoc-markdown", "lazydocs", "portray",
    "interrogate", "darglint", "docformatter", "griffe", "mike",
    "towncrier", "gitchangelog", "mkdocstrings", "breathe",
    "sphinx-autobuild", "myst-parser", "sphinx-copybutton",
    # ── HTTP & API clients ────────────────────────────────────────────────
    "httpie", "posting", "hurl",
    # ── Database CLI ──────────────────────────────────────────────────────
    "pgcli", "mycli", "litecli", "iredis", "sqlite-utils", "datasette",
    "csvkit", "visidata", "alembic", "yoyo-migrations", "pg-activity",
    "pgspecial", "sqlacodegen",
    # ── DevOps & Cloud ────────────────────────────────────────────────────
    "ansible", "ansible-lint", "ansible-core", "molecule", "fabric",
    "invoke", "awscli", "sam-cli", "chalice", "zappa", "sceptre",
    "cfn-lint", "checkov", "troposphere",
    # ── Monitoring & Profiling ────────────────────────────────────────────
    "glances", "bpytop", "speedtest-cli", "memory-profiler", "py-spy",
    "scalene", "pyinstrument", "line-profiler",
    # ── Security ──────────────────────────────────────────────────────────
    "trufflehog", "detect-secrets", "sqlmap", "pwntools", "impacket",
    "ossaudit", "liccheck", "pip-licenses",
    # ── Data Science & Jupyter ────────────────────────────────────────────
    "jupyterlab", "jupyter", "ipython", "notebook", "nbconvert",
    "nbformat", "nbstripout", "nbqa", "papermill", "ploomber", "kedro",
    "mlflow", "dvc", "wandb", "prefect", "great-expectations", "evidently",
    "nbdime", "nbval", "ydata-profiling", "sweetviz",
    # ── NLP ───────────────────────────────────────────────────────────────
    "spacy", "nltk", "textblob", "gensim",
    # ── Data Science Libraries ────────────────────────────────────────────
    "pandas", "polars", "numpy", "scipy", "scikit-learn", "xgboost", "lightgbm",
    # ── Visualization ─────────────────────────────────────────────────────
    "matplotlib", "plotly", "seaborn", "altair", "bokeh",
    # ── Media & Content ───────────────────────────────────────────────────
    "yt-dlp", "gallery-dl", "beets", "spotdl", "scdl", "photini", "pytubefix",
    # ── Terminal & Shell Utilities ────────────────────────────────────────
    "rich-cli", "asciinema", "tldr", "cheat", "ranger", "pyfiglet",
    "cowsay", "thefuck", "howdoi", "textual", "termtosvg",
    "xonsh", "ptpython", "bpython", "ipdb", "pudb",
    # ── Git Tools ─────────────────────────────────────────────────────────
    "pre-commit", "commitizen", "gitlint", "gitchangelog", "git-fame",
    "gita", "gitpython", "pygithub",
    # ── Web Servers ───────────────────────────────────────────────────────
    "uvicorn", "gunicorn", "hypercorn", "daphne", "granian", "waitress",
    # ── Web Frameworks ────────────────────────────────────────────────────
    "django", "flask", "fastapi", "starlette", "tornado", "bottle",
    "falcon", "sanic", "quart", "connexion",
    # ── Web Scraping ──────────────────────────────────────────────────────
    "scrapy", "playwright", "mechanize", "beautifulsoup4", "selenium",
    # ── Task Queues ───────────────────────────────────────────────────────
    "celery", "rq", "dramatiq", "huey", "arq",
    # ── ORM & Database Libs ──────────────────────────────────────────────
    "sqlalchemy", "peewee", "piccolo", "tortoise-orm",
    # ── Config & Data Formats ────────────────────────────────────────────
    "yamllint", "jsonschema", "yq", "datamodel-code-generator",
    # ── Task Runners ──────────────────────────────────────────────────────
    "doit", "poethepoet", "taskipy",
    # ── Project Scaffolding ───────────────────────────────────────────────
    "cookiecutter", "cruft", "copier",
    # ── Network Tools ─────────────────────────────────────────────────────
    "mitmproxy", "scapy", "paramiko", "pysftp", "netaddr",
    # ── Python Environment ────────────────────────────────────────────────
    "virtualenv", "virtualenvwrapper", "pipx",
    # ── Code Formatters ───────────────────────────────────────────────────
    "yapf", "darker",
    # ── CLI Frameworks & Input ────────────────────────────────────────────
    "click", "typer", "docopt", "argcomplete", "prompt-toolkit",
    "questionary", "halo", "yaspin",
    # ── Terminal Output & Progress ────────────────────────────────────────
    "rich", "colorama", "blessed", "urwid", "tqdm", "alive-progress",
    # ── Serialization ─────────────────────────────────────────────────────
    "marshmallow", "cattrs", "dacite", "msgpack",
    # ── Configuration ─────────────────────────────────────────────────────
    "dynaconf", "python-decouple", "environs",
    # ── Time & Date ───────────────────────────────────────────────────────
    "pendulum", "arrow", "python-dateutil", "humanize",
    # ── Text Processing ───────────────────────────────────────────────────
    "unidecode", "ftfy", "chardet",
    # ── Retry & Resilience ────────────────────────────────────────────────
    "tenacity", "backoff",
    # ── Scheduling ────────────────────────────────────────────────────────
    "schedule", "apscheduler",
    # ── File Watching ─────────────────────────────────────────────────────
    "watchdog", "watchfiles",
    # ── Crypto & Security Libs ────────────────────────────────────────────
    "cryptography", "pycryptodome", "passlib",
    # ── GraphQL ───────────────────────────────────────────────────────────
    "strawberry-graphql", "gql", "ariadne",
    # ── Image Processing ─────────────────────────────────────────────────
    "pillow", "wand", "imageio",
    # ── PDF & Office ─────────────────────────────────────────────────────
    "pypdf", "reportlab", "fpdf2", "openpyxl", "python-docx",
    # ── Debugging ─────────────────────────────────────────────────────────
    "snoop", "icecream", "pdbpp",
    # ── Async Helpers ─────────────────────────────────────────────────────
    "trio", "anyio", "aiofiles",
    # ── Logging ───────────────────────────────────────────────────────────
    "loguru", "structlog",
    # ── HTTP Clients ──────────────────────────────────────────────────────
    "httpx", "aiohttp", "requests",
    # ── Data Validation ───────────────────────────────────────────────────
    "pydantic", "attrs", "cerberus",
    # ── Miscellaneous ─────────────────────────────────────────────────────
    "pygments", "python-dotenv", "toml", "tomli", "click-repl",
    "tabulate", "prettytable", "termcolor", "cachetools",
    "python-magic", "chardet", "charset-normalizer",
    "more-itertools", "toolz", "funcy", "boltons",
]]

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def find_pipx() -> Optional[str]:
    """Locate the pipx executable. Checks prefs custom path first."""
    global _pipx_path

    prefs = load_prefs()
    custom = prefs.get("pipx_path", "").strip()
    if custom and os.path.isfile(custom) and os.access(custom, os.X_OK):
        _pipx_path = custom
        return _pipx_path

    if _pipx_path and os.path.isfile(_pipx_path):
        return _pipx_path

    candidate = shutil.which("pipx")
    if candidate:
        _pipx_path = candidate
        return _pipx_path

    for p in (
        os.path.expanduser("~/.local/bin/pipx"),
        "/usr/bin/pipx",
        "/usr/local/bin/pipx",
    ):
        if os.path.isfile(p) and os.access(p, os.X_OK):
            _pipx_path = p
            return _pipx_path

    return None


def invalidate_pipx_cache() -> None:
    """Force re-detection on next find_pipx() call."""
    global _pipx_path
    _pipx_path = None


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def _get_env() -> dict[str, str]:
    env = os.environ.copy()
    pipx = find_pipx()
    if pipx:
        pipx_bin = os.path.dirname(pipx)
        current_path = env.get("PATH", "")
        if pipx_bin not in current_path.split(os.pathsep):
            env["PATH"] = f"{pipx_bin}{os.pathsep}{current_path}"
    # Also ensure ~/.local/bin is in PATH for installed apps
    local_bin = os.path.expanduser("~/.local/bin")
    current_path = env.get("PATH", "")
    if local_bin not in current_path.split(os.pathsep):
        env["PATH"] = f"{local_bin}{os.pathsep}{current_path}"
    return env


# ---------------------------------------------------------------------------
# Core runners
# ---------------------------------------------------------------------------

def run_pipx_async(
    args: list[str],
    on_line: Optional[Callable[[str], None]],
    on_complete: Optional[Callable[[int, str], None]],
) -> None:
    """Run pipx <args> in a daemon thread, streaming output via GLib.idle_add."""

    def _worker() -> None:
        pipx = find_pipx()
        if not pipx:
            msg = "Error: pipx not found. Install it from https://pipx.pypa.io/\n"
            if on_line:
                GLib.idle_add(on_line, msg)
            if on_complete:
                GLib.idle_add(on_complete, 1, msg)
            return

        cmd = [pipx] + args
        env = _get_env()
        collected: list[str] = []

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1,
            )
            assert proc.stdout is not None
            for raw_line in proc.stdout:
                collected.append(raw_line)
                if on_line:
                    GLib.idle_add(on_line, raw_line)
            proc.wait()
            returncode = proc.returncode
        except OSError as exc:
            error = f"Error executing pipx: {exc}\n"
            if on_line:
                GLib.idle_add(on_line, error)
            if on_complete:
                GLib.idle_add(on_complete, 1, error)
            return

        full_output = "".join(collected)
        if on_complete:
            GLib.idle_add(on_complete, returncode, full_output)

    threading.Thread(target=_worker, daemon=True).start()


def run_pipx_sync(args: list[str]) -> tuple[int, str]:
    """Run pipx <args> synchronously. For background data-fetch threads only."""
    pipx = find_pipx()
    if not pipx:
        return 1, ""
    cmd = [pipx] + args
    env = _get_env()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=env, timeout=60
        )
        return result.returncode, result.stdout
    except OSError as exc:
        return 1, str(exc)
    except subprocess.TimeoutExpired:
        return 1, "Timeout waiting for pipx"


# ---------------------------------------------------------------------------
# Data queries
# ---------------------------------------------------------------------------

def _read_venvs_from_disk() -> list[dict]:
    """Read package metadata directly from PIPX_HOME venv directories.

    Used as a fallback when `pipx list --json` fails (e.g. due to a venv
    whose pipx_metadata_version is unknown to the installed pipx).
    """
    pipx_home = os.environ.get("PIPX_HOME", os.path.expanduser("~/.local/share/pipx"))
    venvs_dir = os.path.join(pipx_home, "venvs")
    packages: list[dict] = []
    try:
        venv_names = sorted(os.listdir(venvs_dir))
    except OSError:
        return packages

    for venv_name in venv_names:
        meta_path = os.path.join(venvs_dir, venv_name, "pipx_metadata.json")
        try:
            with open(meta_path) as fh:
                meta = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue

        main_pkg = meta.get("main_package", {})
        injected = meta.get("injected_packages", {})
        packages.append({
            "name": main_pkg.get("package", venv_name),
            "version": main_pkg.get("package_version", ""),
            "python_version": meta.get("python_version", ""),
            "apps": main_pkg.get("apps", []),
            "injected": list(injected.keys()),
            "venv_location": os.path.join(venvs_dir, venv_name),
            "status": "installed",
            "latest_version": "",
        })

    return packages


def get_installed_packages(callback: Callable[[list[dict]], None]) -> None:
    """Parse `pipx list --json` and call callback with list of package dicts.

    Falls back to reading venv metadata directly from disk if the pipx
    command fails (e.g. a venv with an unknown metadata version).
    """

    def _worker() -> None:
        rc, out = run_pipx_sync(["list", "--json"])
        packages: list[dict] = []

        if rc == 0 and out.strip():
            try:
                data = json.loads(out)
                venvs = data.get("venvs", {})
                for venv_name, venv_data in venvs.items():
                    meta = venv_data.get("metadata", {})
                    main_pkg = meta.get("main_package", {})
                    injected = meta.get("injected_packages", {})

                    pipx_home = os.environ.get(
                        "PIPX_HOME",
                        os.path.expanduser("~/.local/share/pipx")
                    )
                    packages.append({
                        "name": main_pkg.get("package", venv_name),
                        "version": main_pkg.get("package_version", ""),
                        "python_version": meta.get("python_version", ""),
                        "apps": main_pkg.get("apps", []),
                        "injected": list(injected.keys()),
                        "venv_location": os.path.join(pipx_home, "venvs", venv_name),
                        "status": "installed",
                        "latest_version": "",
                    })
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        if not packages:
            packages = _read_venvs_from_disk()

        GLib.idle_add(callback, packages)

    threading.Thread(target=_worker, daemon=True).start()


def query_pypi(name: str, callback: Callable[[Optional[dict]], None]) -> None:
    """Query PyPI JSON API for a package. Calls callback with info dict or None."""

    def _worker() -> None:
        url = f"https://pypi.org/pypi/{name}/json"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Linepipe/1.0 (https://github.com/Torcken/linepipe)"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            info = data.get("info", {})
            result = {
                "name": info.get("name", name),
                "version": info.get("version", ""),
                "summary": info.get("summary", ""),
                "home_page": info.get("home_page", "") or info.get("project_url", ""),
                "license": info.get("license", ""),
                "author": info.get("author", ""),
                "requires_python": info.get("requires_python", ""),
            }
            GLib.idle_add(callback, result)
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
            GLib.idle_add(callback, None)

    threading.Thread(target=_worker, daemon=True).start()


def check_pypi_versions(
    packages: list[dict],
    on_result: Callable[[str, str], None],
    show_prerelease: bool = False,
) -> None:
    """For each package, check latest PyPI version. Calls on_result(name, latest_version)."""

    def _check_one(pkg: dict) -> None:
        name = pkg["name"]
        url = f"https://pypi.org/pypi/{name}/json"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Linepipe/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            info = data.get("info", {})
            latest = info.get("version", "")
            GLib.idle_add(on_result, name, latest)
        except Exception:
            GLib.idle_add(on_result, name, "")

    def _worker() -> None:
        for pkg in packages:
            _check_one(pkg)

    threading.Thread(target=_worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Mutating actions
# ---------------------------------------------------------------------------

def install_package(
    name: str,
    version_spec: str = "",
    include_deps: bool = False,
    python_path: str = "",
    on_line: Optional[Callable[[str], None]] = None,
    on_complete: Optional[Callable[[int, str], None]] = None,
) -> None:
    pkg = f"{name}{version_spec}" if version_spec else name
    args = ["install", pkg]
    if include_deps:
        args.append("--include-deps")
    if python_path:
        args += ["--python", python_path]
    run_pipx_async(args, on_line, on_complete)


def uninstall_package(
    name: str,
    on_line: Optional[Callable[[str], None]] = None,
    on_complete: Optional[Callable[[int, str], None]] = None,
) -> None:
    run_pipx_async(["uninstall", name], on_line, on_complete)


def upgrade_package(
    name: str,
    on_line: Optional[Callable[[str], None]] = None,
    on_complete: Optional[Callable[[int, str], None]] = None,
) -> None:
    run_pipx_async(["upgrade", name], on_line, on_complete)


def upgrade_all_packages(
    on_line: Optional[Callable[[str], None]] = None,
    on_complete: Optional[Callable[[int, str], None]] = None,
) -> None:
    run_pipx_async(["upgrade-all"], on_line, on_complete)


def inject_packages(
    pkg_name: str,
    deps: list[str],
    on_line: Optional[Callable[[str], None]] = None,
    on_complete: Optional[Callable[[int, str], None]] = None,
) -> None:
    run_pipx_async(["inject", pkg_name] + deps, on_line, on_complete)


def uninject_package(
    pkg_name: str,
    dep: str,
    on_line: Optional[Callable[[str], None]] = None,
    on_complete: Optional[Callable[[int, str], None]] = None,
) -> None:
    run_pipx_async(["uninject", pkg_name, dep], on_line, on_complete)


def run_app(
    app_name: str,
    extra_args: list[str],
    on_line: Optional[Callable[[str], None]] = None,
    on_complete: Optional[Callable[[int, str], None]] = None,
) -> None:
    run_pipx_async(["run", app_name] + extra_args, on_line, on_complete)


def reinstall_all(
    on_line: Optional[Callable[[str], None]] = None,
    on_complete: Optional[Callable[[int, str], None]] = None,
) -> None:
    run_pipx_async(["reinstall-all"], on_line, on_complete)
