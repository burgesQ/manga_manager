"""UI-free helpers behind the Projects and History pages.

- **projects**: create a project (optionally prefilled from an existing folder's
  ``packer.json`` / ``.batch``), duplicate a profile under a new name;
- **runs**: overall run status, one-line run summaries, duration / date display.

Nothing here imports NiceGUI, so all of it is unit-tested directly.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

from packer.cli import _resolve_config_path, load_config_file, parse_batch_file
from packer.core import NAMED_PATTERNS, find_cbz_files

from .forms import StepStatus, parse_path
from .models import Kind, Project, slugify
from .runner import PipelineResult
from .store import RunRecord, Store

logger = logging.getLogger(__name__)

PACKER_JSON = "packer.json"
BATCH_FILENAME = ".batch"


# ---------------------------------------------------------------------------
# Projects: create from folder, duplicate
# ---------------------------------------------------------------------------


class FolderDetection(NamedTuple):
    """What an existing source folder already provides.

    - ``config_path``: ``<source>/packer.json`` when present (even if invalid);
    - ``config``: its content (``{}`` when absent or invalid);
    - ``batch_file``: the batch CSV packer would use (``batch_file`` of
      ``packer.json``, else the auto-discovered ``<source>/.batch``) when it exists;
    - ``batch_volumes``: number of volumes in that batch file (``None`` if unreadable);
    - ``cbz_count``: ``.cbz`` archives directly in the folder;
    - ``errors``: problems met (invalid ``packer.json`` / batch file …).
    """

    source: Path
    exists: bool
    config_path: Path | None
    config: dict[str, Any]
    batch_file: Path | None
    batch_volumes: int | None
    cbz_count: int
    errors: list[str]

    @property
    def serie(self) -> str | None:
        value = self.config.get("serie")
        return value if isinstance(value, str) and value.strip() else None

    @property
    def pattern(self) -> str | None:
        """Named pattern of ``packer.json`` (``None`` when absent or unknown)."""
        value = self.config.get("pattern")
        return value if value in NAMED_PATTERNS else None

    @property
    def kind(self) -> Kind | None:
        value = self.config.get("kind")
        return Kind(value) if value in {k.value for k in Kind} else None


def detect_folder(source: Path) -> FolderDetection:
    """Inspect ``source`` for ``packer.json``, a batch file and ``.cbz`` archives.

    Never raises: problems end up in ``errors``.
    """
    errors: list[str] = []
    if not source.is_dir():
        return FolderDetection(source, False, None, {}, None, None, 0, errors)

    config_path: Path | None = None
    config: dict[str, Any] = {}
    cfg = source / PACKER_JSON
    if cfg.is_file():
        config_path = cfg
        try:
            config = load_config_file(str(cfg))
        except ValueError as e:
            errors.append(str(e))

    batch_file: Path | None = None
    cfg_batch = config.get("batch_file") or config.get("batch")
    candidates = [source / BATCH_FILENAME]
    if cfg_batch:
        candidates.insert(0, Path(_resolve_config_path(str(cfg_batch), str(source))))
    for candidate in candidates:
        if candidate.is_file():
            batch_file = candidate
            break
    batch_volumes: int | None = None
    if batch_file is not None:
        try:
            batch_volumes = len(parse_batch_file(str(batch_file)))
        except (ValueError, OSError) as e:
            errors.append(f"invalid batch file {batch_file}: {e}")

    try:
        cbz_count = len(find_cbz_files(str(source)))
    except OSError as e:
        errors.append(f"cannot list {source}: {e}")
        cbz_count = 0
    return FolderDetection(
        source, True, config_path, config, batch_file, batch_volumes, cbz_count, errors
    )


def describe_detection(detection: FolderDetection) -> list[str]:
    """Human-readable lines describing ``detection`` (for the New project form)."""
    if not detection.exists:
        return [f"Folder not found: {detection.source} (it can be created later)"]
    lines = [f"{detection.cbz_count} .cbz archive(s)"]
    if detection.config_path is None:
        lines.append("No packer.json")
    else:
        found = [
            f"{key}={value}"
            for key, value in (
                ("serie", detection.serie),
                ("pattern", detection.pattern),
                ("kind", detection.kind.value if detection.kind else None),
            )
            if value
        ]
        lines.append(
            f"packer.json found ({', '.join(found) or 'no serie / pattern / kind'})"
        )
    if detection.batch_file is not None:
        count = (
            f"{detection.batch_volumes} volume(s)"
            if detection.batch_volumes is not None
            else "unreadable"
        )
        lines.append(f"Batch file: {detection.batch_file.name} ({count})")
    lines.extend(f"Error: {e}" for e in detection.errors)
    return lines


def new_project(
    name: str,
    source: Path,
    *,
    kind: Kind | None = None,
    detection: FolderDetection | None = None,
) -> Project:
    """Build (not save) a project, prefilled from ``detection`` when given.

    With a ``packer.json`` in the folder, ``packer.config`` points to it and
    ``serie`` / ``pattern`` / ``kind`` are copied from it. An explicit ``kind`` wins
    over the one of ``packer.json``. The batch file is not copied: packer finds it
    on its own (``batch_file`` key or ``<source>/.batch``), and the wizard's
    "Batch file" mode edits that same file.
    """
    project = Project(name=name, source=source)
    if detection is not None and detection.config_path is not None:
        opts = project.packer
        opts.config = detection.config_path
        opts.serie = detection.serie
        opts.pattern = detection.pattern or opts.pattern
        if detection.kind is not None:
            project.kind = detection.kind
    if kind is not None:
        project.kind = kind
    return project


def create_project(
    store: Store,
    name: str,
    source_text: str,
    *,
    kind: Kind | None = None,
    from_folder: bool = True,
) -> Project:
    """Create and save a new project; raises ``ValueError`` with a user message.

    With ``from_folder`` the source folder is inspected (:func:`detect_folder`) to
    prefill the profile. An invalid ``packer.json`` is not refused (nothing is
    prefilled from it): the wizard reports it and its raw editor can fix it.
    """
    name = name.strip()
    source = parse_path(source_text)
    if not name:
        raise ValueError("project name is required")
    if source is None:
        raise ValueError("source folder is required")
    slug = slugify(name)
    if store.has_project(slug):
        raise ValueError(f"a project with slug {slug!r} already exists")
    detection = detect_folder(source) if from_folder else None
    project = new_project(name, source, kind=kind, detection=detection)
    store.save_project(project)
    logger.info("created project %s (%s)", project.slug, source)
    return project


def duplicate_profile(project: Project, new_name: str) -> Project:
    """Deep copy of ``project`` renamed to ``new_name`` (new slug).

    >>> src = Project(name="Saga", source=Path("/lib"))
    >>> dup = duplicate_profile(src, "Saga (colour)")
    >>> (dup.name, dup.slug, dup.source == src.source, dup.packer is src.packer)
    ('Saga (colour)', 'saga-colour', True, False)
    """
    name = new_name.strip()
    if not name:
        raise ValueError("new project name is required")
    data = project.to_dict()
    data["name"] = name
    data["slug"] = slugify(name)
    return Project.from_dict(data)


def duplicate_project(store: Store, slug: str, new_name: str) -> Project:
    """Copy the profile ``slug`` to a new project (run history is not copied)."""
    project = duplicate_profile(store.load_project(slug), new_name)
    if store.has_project(project.slug):
        raise ValueError(f"a project with slug {project.slug!r} already exists")
    store.save_project(project)
    logger.info("duplicated project %s as %s", slug, project.slug)
    return project


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


class StepSummary(NamedTuple):
    step: str
    exit_code: int
    status: StepStatus
    duration: float
    argv: list[str]


class RunSummary(NamedTuple):
    """Display data of one stored run."""

    run_id: str
    started_at: str
    dry_run: bool
    duration: float
    status: StepStatus
    exit_code: int
    steps: list[StepSummary]

    @property
    def label(self) -> str:
        """``"ok · 2026-01-02 10:00:00 (dry-run)"``-style one-liner."""
        mode = " (dry-run)" if self.dry_run else ""
        return f"{self.status.value} · {format_started_at(self.started_at)}{mode}"


def run_status(result: PipelineResult) -> StepStatus:
    """Overall status of a run: cancelled, ok, or failed."""
    if result.cancelled:
        return StepStatus.CANCELLED
    return StepStatus.OK if result.exit_code == 0 else StepStatus.FAILED


def summarize_run(record: RunRecord) -> RunSummary:
    result = record.result
    steps = [
        StepSummary(
            step=s.step,
            exit_code=s.exit_code,
            status=(
                StepStatus.CANCELLED
                if s.cancelled
                else StepStatus.OK if s.exit_code == 0 else StepStatus.FAILED
            ),
            duration=s.duration,
            argv=list(s.argv),
        )
        for s in result.steps
    ]
    return RunSummary(
        run_id=record.run_id,
        started_at=result.started_at,
        dry_run=result.dry_run,
        duration=result.duration,
        status=run_status(result),
        exit_code=result.exit_code,
        steps=steps,
    )


def run_summaries(store: Store, slug: str) -> list[RunSummary]:
    """Summaries of every stored run of ``slug``, newest first."""
    return [summarize_run(r) for r in store.list_runs(slug)]


def last_run_summary(store: Store, slug: str) -> RunSummary | None:
    """Summary of the newest run of ``slug`` (``None`` if it never ran)."""
    runs = store.list_runs(slug)
    return summarize_run(runs[0]) if runs else None


def format_duration(seconds: float) -> str:
    """Compact duration.

    >>> [format_duration(s) for s in (0.42, 12.34, 125, 3725)]
    ['0.4s', '12.3s', '2m 05s', '1h 02m']
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m {secs:02d}s"


def format_started_at(value: str) -> str:
    """ISO timestamp as ``YYYY-mm-dd HH:MM:SS`` (unchanged when not ISO).

    >>> format_started_at("2026-01-02T10:11:12+01:00")
    '2026-01-02 10:11:12'
    >>> format_started_at("?")
    '?'
    """
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value
