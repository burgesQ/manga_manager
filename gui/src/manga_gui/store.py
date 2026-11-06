"""Persistence of project profiles and run history.

Default layout (XDG):

- projects: ``$XDG_CONFIG_HOME/manga_manager/projects/<slug>.json``
  (``~/.config/...`` when unset)
- runs: ``$XDG_STATE_HOME/manga_manager/runs/<slug>/<run_id>.{json,log}``
  (``~/.local/state/...`` when unset)

With an explicit ``data_dir`` (``manga-gui --data-dir``, tests, alternative
profile dirs) both live under it: ``<data_dir>/projects`` and ``<data_dir>/runs``.

App settings (:class:`~manga_gui.models.Settings`: library root, metadata dir) live
next to the projects: ``<config>/settings.json`` (``<data_dir>/settings.json``).
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

from .models import Project, Settings
from .runner import PipelineResult

logger = logging.getLogger(__name__)

APP_DIR_NAME = "manga_manager"
SETTINGS_FILENAME = "settings.json"
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_RUN_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}-[0-9]{6}$")


class RunRecord(NamedTuple):
    """A stored run: its id (timestamp), result and the path of its log file."""

    run_id: str
    result: PipelineResult
    log_path: Path


def _xdg_dir(env_var: str, fallback: str) -> Path:
    value = os.environ.get(env_var)
    base = Path(value) if value else Path.home() / fallback
    return base / APP_DIR_NAME


def _check_slug(slug: str) -> str:
    if not _SLUG_RE.match(slug):
        raise ValueError(f"invalid project slug: {slug!r}")
    return slug


def _check_run_id(run_id: str) -> str:
    if not _RUN_ID_RE.match(run_id):
        raise ValueError(f"invalid run id: {run_id!r}")
    return run_id


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


class Store:
    """File-based store for :class:`Project` profiles and :class:`RunRecord` runs."""

    def __init__(
        self,
        data_dir: Path | None = None,
        *,
        settings_overrides: Settings | None = None,
    ) -> None:
        if data_dir is not None:
            config_dir = Path(data_dir)
            self.runs_dir = Path(data_dir) / "runs"
        else:
            config_dir = _xdg_dir("XDG_CONFIG_HOME", ".config")
            self.runs_dir = _xdg_dir("XDG_STATE_HOME", ".local/state") / "runs"
        self.projects_dir = config_dir / "projects"
        self.settings_path = config_dir / SETTINGS_FILENAME
        # Session values (``manga-gui --library-root …``) winning over the file.
        self.settings_overrides = settings_overrides or Settings()

    # -- settings ---------------------------------------------------------

    def load_settings(self) -> Settings:
        """Saved settings (defaults when the file is missing or unreadable)."""
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return Settings()
        except (OSError, ValueError) as e:
            logger.warning("ignoring unreadable settings %s: %s", self.settings_path, e)
            return Settings()
        if not isinstance(data, dict):
            logger.warning("ignoring settings %s: not an object", self.settings_path)
            return Settings()
        return Settings.from_dict(data)

    def _write_settings(self, settings: Settings) -> Path:
        text = json.dumps(settings.to_dict(), indent=2, ensure_ascii=False)
        _write_atomic(self.settings_path, text + "\n")
        return self.settings_path

    def save_settings(self, settings: Settings) -> Path:
        """Write ``settings`` atomically; they replace the session overrides."""
        path = self._write_settings(settings)
        self.settings_overrides = Settings()
        return path

    def save_theme(self, theme: str) -> Path:
        """Store ``theme`` in the saved settings, keeping everything else.

        Unlike :meth:`save_settings`, the session overrides stay active (the
        theme switch must not save ``--library-root`` / ``--metadata-dir``).
        """
        return self._write_settings(replace(self.load_settings(), theme=theme))

    def effective_settings(self) -> Settings:
        """Saved settings with the session overrides applied."""
        return self.load_settings().merged(self.settings_overrides)

    # -- projects ---------------------------------------------------------

    def project_path(self, slug: str) -> Path:
        """Path of the JSON profile for ``slug`` (may not exist)."""
        return self.projects_dir / f"{_check_slug(slug)}.json"

    def list_projects(self) -> list[Project]:
        """All readable projects, sorted by name. Unreadable files are skipped."""
        if not self.projects_dir.is_dir():
            return []
        projects: list[Project] = []
        for path in sorted(self.projects_dir.glob("*.json")):
            try:
                projects.append(self._read_project(path))
            except (OSError, ValueError, KeyError, TypeError) as e:
                logger.warning("skipping unreadable project %s: %s", path, e)
        return sorted(projects, key=lambda p: (p.name.lower(), p.slug))

    def _read_project(self, path: Path) -> Project:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("top-level JSON must be an object")
        return Project.from_dict(data)

    def load_project(self, slug: str) -> Project:
        """Load a project. Raises ``FileNotFoundError`` if it does not exist."""
        return self._read_project(self.project_path(slug))

    def has_project(self, slug: str) -> bool:
        return self.project_path(slug).exists()

    def save_project(self, project: Project) -> Path:
        """Write ``project`` atomically to ``<projects>/<slug>.json``."""
        path = self.project_path(project.slug)
        text = json.dumps(project.to_dict(), indent=2, ensure_ascii=False)
        _write_atomic(path, text + "\n")
        return path

    def delete_project(self, slug: str, *, purge_runs: bool = False) -> bool:
        """Delete a project profile (and its run history if ``purge_runs``).

        Returns True if the profile existed.
        """
        path = self.project_path(slug)
        existed = path.exists()
        path.unlink(missing_ok=True)
        if purge_runs:
            shutil.rmtree(self.runs_dir / slug, ignore_errors=True)
        return existed

    # -- runs -------------------------------------------------------------

    def _run_dir(self, slug: str) -> Path:
        return self.runs_dir / _check_slug(slug)

    def save_run(self, slug: str, result: PipelineResult, log_text: str) -> RunRecord:
        """Store a run as ``<run_id>.json`` + ``<run_id>.log`` and return it.

        ``run_id`` is a local timestamp ``YYYYmmddTHHMMSS-ffffff``.
        """
        run_dir = self._run_dir(slug)
        run_id = datetime.now().strftime("%Y%m%dT%H%M%S-%f")
        while (run_dir / f"{run_id}.json").exists():  # pragma: no cover - same µs
            run_id = datetime.now().strftime("%Y%m%dT%H%M%S-%f")
        log_path = run_dir / f"{run_id}.log"
        _write_atomic(log_path, log_text)
        payload: dict[str, Any] = {"run_id": run_id, **result.to_dict()}
        _write_atomic(run_dir / f"{run_id}.json", json.dumps(payload, indent=2) + "\n")
        return RunRecord(run_id=run_id, result=result, log_path=log_path)

    def load_run(self, slug: str, run_id: str) -> RunRecord:
        """Load one run. Raises ``FileNotFoundError`` if it does not exist."""
        run_dir = self._run_dir(slug)
        _check_run_id(run_id)
        data = json.loads((run_dir / f"{run_id}.json").read_text(encoding="utf-8"))
        return RunRecord(
            run_id=run_id,
            result=PipelineResult.from_dict(data),
            log_path=run_dir / f"{run_id}.log",
        )

    def read_run_log(self, slug: str, run_id: str) -> str:
        """Return the log text of a run ("" if the log file is missing)."""
        record_log = self._run_dir(slug) / f"{_check_run_id(run_id)}.log"
        try:
            return record_log.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ""

    def list_runs(self, slug: str) -> list[RunRecord]:
        """All readable runs of ``slug``, newest first."""
        run_dir = self._run_dir(slug)
        if not run_dir.is_dir():
            return []
        records: list[RunRecord] = []
        for path in sorted(run_dir.glob("*.json"), reverse=True):
            if not _RUN_ID_RE.match(path.stem):
                continue
            try:
                records.append(self.load_run(slug, path.stem))
            except (OSError, ValueError, KeyError, TypeError) as e:
                logger.warning("skipping unreadable run %s: %s", path, e)
        return records

    def delete_run(self, slug: str, run_id: str) -> None:
        run_dir = self._run_dir(slug)
        _check_run_id(run_id)
        for suffix in (".json", ".log"):
            (run_dir / f"{run_id}{suffix}").unlink(missing_ok=True)
