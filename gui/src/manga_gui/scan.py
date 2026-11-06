"""Read-only library scans: chapter detection preview, volume folders, EPUBs.

Chapter detection reuses ``packer.core.find_cbz_files`` and
``packer.core.extract_chapter_number`` with the patterns packer would use (named
pattern or custom regexes, merged with ``packer.json``), so the preview matches what
``packer`` will do.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

from packer.core import extract_chapter_number, find_cbz_files

from .models import Project
from .validation import (
    PackerSettings,
    compile_patterns,
    resolve_batch_specs,
    resolve_packer_settings,
)

COVER_FILENAME = "cover.webp"
_VOLUME_RE = re.compile(r"\bv0*([0-9]+)$", re.IGNORECASE)


class ScannedChapter(NamedTuple):
    """A ``.cbz`` file matched to a chapter (``extra`` is set for ``16.5``-style)."""

    number: int
    extra: str | None
    file: Path

    @property
    def label(self) -> str:
        return f"{self.number}.{self.extra}" if self.extra else str(self.number)


class ScanResult(NamedTuple):
    """Outcome of :func:`scan_library`.

    - ``chapters``: matches sorted by (number, extra);
    - ``unmatched``: ``.cbz`` files no pattern recognised;
    - ``duplicates``: chapter number → files when several *main* archives match
      (packer aborts with DUPLICATE_CHAPTER on those);
    - ``missing``: chapters requested by the batch / range but not found;
    - ``errors``: config / regex / filesystem problems met while scanning.
    """

    chapters: list[ScannedChapter]
    unmatched: list[Path]
    duplicates: dict[int, list[Path]]
    missing: list[int]
    errors: list[str]


class VolumeDir(NamedTuple):
    """A volume folder under the destination root (as convertor sees it)."""

    path: Path
    volume: int | None
    chapters: int
    cover: Path | None
    epub: Path | None

    @property
    def name(self) -> str:
        return self.path.name


def _extra_key(extra: str | None) -> tuple[int, str]:
    if extra is None:
        return (-1, "")
    return (int(extra), extra) if extra.isdigit() else (1 << 30, extra)


def _settings_or_fallback(project: Project, errors: list[str]) -> PackerSettings:
    try:
        return resolve_packer_settings(project)
    except ValueError as e:
        errors.append(str(e))
    opts = project.packer
    return PackerSettings(
        config_path=project.source / "packer.json",
        config={},
        serie=opts.serie,
        pattern=opts.pattern,
        chapter_regex=opts.chapter_regex,
        extra_regex=opts.extra_regex,
        nb_worker=opts.nb_worker,
        batch=opts.batch,
        batch_file=opts.batch_file,
        volume=opts.volume,
        chapter_range=opts.chapter_range,
        covers={},
    )


def scan_library(project: Project) -> ScanResult:
    """Match every ``.cbz`` in ``project.source`` to a chapter number."""
    errors: list[str] = []
    settings = _settings_or_fallback(project, errors)
    try:
        chapter_pat, extra_pat = compile_patterns(settings)
    except re.error as e:
        errors.append(f"invalid regex: {e}")
        chapter_pat = extra_pat = None

    try:
        files = sorted(find_cbz_files(str(project.source)))
    except OSError as e:
        errors.append(f"cannot list {project.source}: {e}")
        files = []

    chapters: list[ScannedChapter] = []
    unmatched: list[Path] = []
    mains: dict[int, list[Path]] = defaultdict(list)
    for f in files:
        matches = extract_chapter_number(
            f, chapter_pat=chapter_pat, extra_pat=extra_pat
        )
        if not matches:
            unmatched.append(Path(f))
            continue
        for m in matches:
            chapters.append(ScannedChapter(m.base, m.extra, Path(f)))
            if m.extra is None:
                mains[m.base].append(Path(f))
    chapters.sort(key=lambda c: (c.number, _extra_key(c.extra), c.file.name))
    duplicates = {n: paths for n, paths in sorted(mains.items()) if len(paths) > 1}

    missing: list[int] = []
    try:
        specs = resolve_batch_specs(settings, project.source)
    except (ValueError, OSError):
        specs = []  # reported by validate_project
    found = {c.number for c in chapters}
    for _, chapter_range in specs:
        missing.extend(n for n in chapter_range if n not in found)

    return ScanResult(
        chapters=chapters,
        unmatched=unmatched,
        duplicates=duplicates,
        missing=sorted(set(missing)),
        errors=errors,
    )


def list_volume_dirs(dest: Path) -> list[VolumeDir]:
    """Immediate sub-folders of ``dest`` (every one is a volume for convertor).

    ``volume`` is parsed from a trailing ``vNN``; ``chapters`` counts the
    ``Chapter *`` sub-folders; ``epub`` is the sibling ``<name>.kepub.epub``.
    """
    if not dest.is_dir():
        return []
    volumes: list[VolumeDir] = []
    for path in sorted(p for p in dest.iterdir() if p.is_dir()):
        m = _VOLUME_RE.search(path.name)
        cover = path / COVER_FILENAME
        epub = dest / f"{path.name}.kepub.epub"
        volumes.append(
            VolumeDir(
                path=path,
                volume=int(m.group(1)) if m else None,
                chapters=sum(
                    1
                    for c in path.iterdir()
                    if c.is_dir() and c.name.startswith("Chapter ")
                ),
                cover=cover if cover.is_file() else None,
                epub=epub if epub.is_file() else None,
            )
        )
    return volumes


def list_epubs(dest: Path) -> list[Path]:
    """``*.epub`` files (``.kepub.epub`` included) directly under ``dest``."""
    if not dest.is_dir():
        return []
    return sorted(
        p for p in dest.iterdir() if p.is_file() and p.name.lower().endswith(".epub")
    )
