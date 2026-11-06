"""Pre-flight validation of a :class:`~manga_gui.models.Project`.

Wraps the loaders of the CLIs instead of reimplementing them:
``packer.cli.load_config_file`` / ``parse_batch_spec`` / ``parse_batch_file`` /
``_resolve_config_path``, ``packer.core.parse_range`` / ``NAMED_PATTERNS``, and
``editor.editor_full.load_yaml_metadata`` / ``_resolve_chapter_titles``. The packer
argument rules mirror ``packer.cli._apply_path_config`` and ``_validate_args``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Literal, NamedTuple

from editor.editor_full import _resolve_chapter_titles, load_yaml_metadata
from packer.cli import (
    _resolve_config_path,
    load_config_file,
    parse_batch_file,
    parse_batch_spec,
)
from packer.core import NAMED_PATTERNS, parse_range

from .models import LOCALES, Project

logger = logging.getLogger(__name__)

Level = Literal["error", "warning"]

KCC_ROTATIONS = (0, 1, 2, 3)
KCC_CROPPINGS = (0, 1, 2)


class Issue(NamedTuple):
    """One validation finding. ``step`` is ``project`` or a pipeline step name."""

    level: Level
    step: str
    message: str


class PackerSettings(NamedTuple):
    """Packer options after merging ``packer.json`` (CLI values win).

    Mirrors ``packer.cli._apply_path_config``; ``batch_file`` and cover paths from
    ``packer.json`` are resolved relative to the config file directory.
    """

    config_path: Path
    config: dict[str, Any]
    serie: str | None
    pattern: str
    chapter_regex: str | None
    extra_regex: str | None
    nb_worker: int
    batch: str | None
    batch_file: Path | None
    volume: int | None
    chapter_range: str | None
    covers: dict[int, Path]


def config_path_for(project: Project) -> Path:
    """``--config`` if set, otherwise ``<source>/packer.json`` (like packer)."""
    if project.packer.config is not None:
        return project.packer.config
    return project.source / "packer.json"


def resolve_packer_settings(project: Project) -> PackerSettings:
    """Merge the project's packer options with ``packer.json``.

    Raises ``ValueError`` (from ``load_config_file``) when the config file is
    invalid, or missing while explicitly configured.
    """
    opts = project.packer
    cfg_path = config_path_for(project)
    cfg = load_config_file(str(cfg_path), required=opts.config is not None)
    base_dir = str(cfg_path.expanduser().absolute().parent)

    pattern = opts.pattern
    if pattern == "default" and "pattern" in cfg:
        pattern = str(cfg["pattern"])
    chapter_regex = opts.chapter_regex
    if chapter_regex is None and "chapter_regex" in cfg:
        chapter_regex = cfg["chapter_regex"]
    extra_regex = opts.extra_regex
    if extra_regex is None and "extra_regex" in cfg:
        extra_regex = cfg["extra_regex"]
    nb_worker = opts.nb_worker
    if nb_worker == 1 and "nb_worker" in cfg:
        nb_worker = int(cfg["nb_worker"])
    batch_file = opts.batch_file
    cfg_batch = cfg.get("batch_file") or cfg.get("batch")
    if batch_file is None and cfg_batch:
        batch_file = Path(_resolve_config_path(str(cfg_batch), base_dir))
    serie = opts.serie
    if serie is None and "serie" in cfg:
        serie = cfg["serie"]

    covers: dict[int, Path] = {}
    raw_covers = cfg.get("covers")
    if isinstance(raw_covers, dict):
        for vol, cover in raw_covers.items():
            try:
                covers[int(vol)] = Path(_resolve_config_path(str(cover), base_dir))
            except (TypeError, ValueError):
                continue

    return PackerSettings(
        config_path=cfg_path,
        config=cfg,
        serie=serie,
        pattern=pattern,
        chapter_regex=chapter_regex,
        extra_regex=extra_regex,
        nb_worker=nb_worker,
        batch=opts.batch,
        batch_file=batch_file,
        volume=opts.volume,
        chapter_range=opts.chapter_range,
        covers=covers,
    )


def compile_patterns(
    settings: PackerSettings,
) -> tuple[re.Pattern[str] | None, re.Pattern[str] | None]:
    """Chapter / extra regexes as packer would use them (``_compile_patterns``).

    Custom regexes win over the named pattern; ``(None, None)`` means packer's
    legacy fallback patterns. Raises ``re.error`` on an invalid custom regex.
    """
    chapter_pat = re.compile(settings.chapter_regex) if settings.chapter_regex else None
    extra_pat = re.compile(settings.extra_regex) if settings.extra_regex else None
    if settings.pattern in NAMED_PATTERNS and not (chapter_pat or extra_pat):
        return NAMED_PATTERNS[settings.pattern]
    return chapter_pat, extra_pat


def resolve_batch_specs(
    settings: PackerSettings, source: Path
) -> list[tuple[int, list[int]]]:
    """Volume → chapters plan packer would execute (``_resolve_batch_specs``).

    Falls back to ``<source>/.batch`` like ``_validate_args``. Returns ``[]`` when
    no volume selection is configured. Raises ``ValueError`` / ``OSError`` on
    unparsable input.
    """
    if settings.batch:
        return parse_batch_spec(settings.batch)
    batch_file = settings.batch_file
    if batch_file is None and (
        settings.volume is None or settings.chapter_range is None
    ):
        discovered = source / ".batch"
        if discovered.exists():
            batch_file = discovered
    if batch_file is not None:
        return parse_batch_file(str(batch_file))
    if settings.volume is not None and settings.chapter_range:
        return [(settings.volume, parse_range(settings.chapter_range))]
    return []


# ---------------------------------------------------------------------------
# Per-step checks
# ---------------------------------------------------------------------------


def _check_project(project: Project) -> list[Issue]:
    issues: list[Issue] = []
    if not project.name.strip():
        issues.append(Issue("error", "project", "project name is empty"))
    if not project.source.is_dir():
        issues.append(
            Issue("error", "project", f"source folder not found: {project.source}")
        )
    dest = project.effective_dest
    if dest.exists() and not dest.is_dir():
        issues.append(Issue("error", "project", f"destination is not a folder: {dest}"))
    if not any(project.steps.values()):
        issues.append(Issue("warning", "project", "no step is enabled"))
    return issues


def _check_regex(pattern: str | None, groups: int, label: str) -> list[Issue]:
    if not pattern:
        return []
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        return [Issue("error", "packer", f"invalid {label}: {e}")]
    if compiled.groups < groups:
        return [
            Issue(
                "warning",
                "packer",
                f"{label} has {compiled.groups} capture group(s), "
                f"packer expects {groups}",
            )
        ]
    return []


def _check_volume_selection(project: Project, s: PackerSettings) -> list[Issue]:
    issues: list[Issue] = []
    opts = project.packer
    # Same truthiness test as packer.cli._validate_args.
    if opts.batch and (opts.volume or opts.chapter_range):
        issues.append(
            Issue("error", "packer", "batch cannot be combined with volume/range")
        )
    if opts.batch and opts.batch_file is not None:
        issues.append(
            Issue("warning", "packer", "both batch and batch file set: batch wins")
        )
    if (
        s.batch_file is not None
        and opts.batch_file is None
        and not opts.batch
        and (opts.volume is not None or opts.chapter_range)
    ):
        issues.append(
            Issue(
                "warning",
                "packer",
                f"packer.json batch file {s.batch_file} overrides volume/range",
            )
        )
    has_single = s.volume is not None and s.chapter_range is not None
    if not (s.batch or s.batch_file or has_single):
        if not (project.source / ".batch").exists():
            issues.append(
                Issue(
                    "error",
                    "packer",
                    "either a batch spec / batch file or both volume and "
                    "chapter range must be provided",
                )
            )
    if s.batch_file is not None and not s.batch and not s.batch_file.is_file():
        issues.append(Issue("error", "packer", f"batch file not found: {s.batch_file}"))
        return issues
    if s.chapter_range and not s.batch:
        try:
            parse_range(s.chapter_range)
        except ValueError as e:
            issues.append(Issue("error", "packer", f"invalid chapter range: {e}"))
    try:
        specs = resolve_batch_specs(s, project.source)
    except (ValueError, OSError) as e:
        issues.append(Issue("error", "packer", f"invalid batch: {e}"))
        return issues
    volumes = [vol for vol, _ in specs]
    dupes = sorted({v for v in volumes if volumes.count(v) > 1})
    if dupes:
        issues.append(
            Issue("warning", "packer", f"volume(s) listed more than once: {dupes}")
        )
    return issues


def _check_packer(project: Project) -> list[Issue]:
    try:
        s = resolve_packer_settings(project)
    except ValueError as e:
        return [Issue("error", "packer", str(e))]

    issues: list[Issue] = []
    if not s.serie:
        issues.append(
            Issue(
                "error",
                "packer",
                "serie is required (project option or `serie` in packer.json)",
            )
        )
    if s.pattern not in ("default", *NAMED_PATTERNS) and not (
        s.chapter_regex or s.extra_regex
    ):
        issues.append(
            Issue(
                "warning",
                "packer",
                f"unknown pattern {s.pattern!r}: packer falls back to the default",
            )
        )
    issues += _check_regex(s.chapter_regex, 1, "chapter regex")
    issues += _check_regex(s.extra_regex, 2, "extra regex")
    if s.nb_worker < 1:
        issues.append(Issue("error", "packer", "nb_worker must be >= 1"))
    issues += _check_volume_selection(project, s)
    for vol, cover in sorted(s.covers.items()):
        if not cover.exists():
            issues.append(
                Issue("warning", "packer", f"cover for volume {vol} not found: {cover}")
            )
    cfg_kind = s.config.get("kind")
    if cfg_kind is not None and str(cfg_kind) != project.kind.value:
        issues.append(
            Issue(
                "warning",
                "packer",
                f"packer.json kind {cfg_kind!r} differs from project kind "
                f"{project.kind.value!r}",
            )
        )
    if project.source.is_dir() and not any(
        p.suffix.lower() == ".cbz" for p in project.source.iterdir()
    ):
        issues.append(Issue("warning", "packer", f"no .cbz file in {project.source}"))
    return issues


def _check_convertor(project: Project) -> list[Issue]:
    issues: list[Issue] = []
    opts = project.convertor
    if opts.rotation is not None and opts.rotation not in KCC_ROTATIONS:
        issues.append(
            Issue("error", "convertor", f"rotation must be one of {KCC_ROTATIONS}")
        )
    if opts.cropping is not None and opts.cropping not in KCC_CROPPINGS:
        issues.append(
            Issue("error", "convertor", f"cropping must be one of {KCC_CROPPINGS}")
        )
    if opts.profile is not None and not opts.profile.strip():
        issues.append(Issue("error", "convertor", "profile is empty"))
    if not project.step_enabled("packer") and not project.effective_dest.is_dir():
        issues.append(
            Issue(
                "error",
                "convertor",
                f"destination folder not found: {project.effective_dest}",
            )
        )
    return issues


def _check_editor(project: Project) -> list[Issue]:
    opts = project.editor
    issues: list[Issue] = []
    if opts.locale not in LOCALES:
        issues.append(
            Issue("error", "editor", f"locale must be one of {', '.join(LOCALES)}")
        )
    if opts.metadata is None:
        issues.append(
            Issue(
                "warning",
                "editor",
                "no metadata YAML configured: the editor step will be skipped",
            )
        )
        return issues
    if not opts.metadata.is_file():
        issues.append(
            Issue("error", "editor", f"metadata YAML not found: {opts.metadata}")
        )
        return issues
    try:
        data = load_yaml_metadata(opts.metadata)
    except Exception as e:  # yaml.YAMLError, OSError, UnicodeDecodeError …
        issues.append(Issue("error", "editor", f"invalid metadata YAML: {e}"))
        return issues
    if not isinstance(data, dict):
        issues.append(
            Issue("error", "editor", "metadata YAML must be a mapping at top level")
        )
        return issues
    volumes = data.get("volumes")
    if not volumes:
        issues.append(Issue("warning", "editor", "metadata YAML has no `volumes`"))
    elif isinstance(volumes, list) and not any(
        isinstance(v, dict) and opts.locale in v for v in volumes
    ):
        issues.append(
            Issue(
                "warning",
                "editor",
                f"no volume has a `{opts.locale}` block (isbn / release_date)",
            )
        )
    try:
        _resolve_chapter_titles(opts.chapters, data, opts.metadata.parent)
    except FileNotFoundError as e:
        issues.append(Issue("error", "editor", f"chapters YAML not found: {e}"))
    except Exception as e:  # malformed chapters YAML
        issues.append(Issue("error", "editor", f"invalid chapters YAML: {e}"))
    return issues


def validate_project(project: Project) -> list[Issue]:
    """Return every issue found for ``project`` (errors first, then warnings).

    Only enabled steps are checked. An empty list means the project is runnable.
    """
    issues = _check_project(project)
    if project.step_enabled("packer"):
        issues += _check_packer(project)
    if project.step_enabled("convertor"):
        issues += _check_convertor(project)
    if project.step_enabled("editor"):
        issues += _check_editor(project)
    return sorted(issues, key=lambda i: i.level != "error")


def has_errors(issues: list[Issue]) -> bool:
    """True when at least one issue is an error."""
    return any(i.level == "error" for i in issues)
