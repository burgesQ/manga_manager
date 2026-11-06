"""UI-free helpers behind the volume previews (G7).

Per-volume preview rows of a destination folder: volume folder, cover, chapter
count, generated ``.kepub.epub`` and the metadata injected into it, read with
:class:`editor.epub_metadata.EPUBMetadata` (read-only). Volumes the batch plans
but packer has not produced yet are listed as ``planned``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, NamedTuple

from editor.editor_full import KIND_TAGS
from editor.epub_metadata import EPUBMetadata
from packer.core import format_volume_dir

from .models import Project
from .scan import _VOLUME_RE, list_epubs, list_volume_dirs
from .validation import resolve_batch_specs, resolve_packer_settings

logger = logging.getLogger(__name__)

_EPUB_SUFFIXES = (".kepub.epub", ".epub")


class EpubInfo(NamedTuple):
    """Metadata read from a generated EPUB (``error`` set when unreadable)."""

    title: str | None = None
    author: str | None = None
    series: str | None = None
    series_index: float | None = None
    tags: tuple[str, ...] = ()
    kind: str | None = None
    language: str | None = None
    isbn: str | None = None
    error: str | None = None

    @property
    def injected(self) -> bool:
        """True when the editor metadata (``calibre:series``) is present."""
        return self.series is not None

    def fields(self) -> list[tuple[str, str]]:
        """Non-empty ``(label, value)`` pairs, in display order."""
        index = self.series_index
        pairs: list[tuple[str, Any]] = [
            ("Title", self.title),
            ("Author", self.author),
            ("Series", self.series),
            ("Index", f"{index:g}" if index is not None else None),
            ("Kind", self.kind),
            ("Tags", ", ".join(self.tags)),
            ("Language", self.language),
            ("ISBN", self.isbn),
        ]
        return [(label, str(value)) for label, value in pairs if value]


def _kind_of(tags: tuple[str, ...]) -> str | None:
    by_tag = {tag.casefold(): kind for kind, tag in KIND_TAGS.items()}
    for tag in tags:
        kind = by_tag.get(tag.casefold())
        if kind is not None:
            return kind
    return None


def _as_text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) or None
    return str(value)


_EPUB_CACHE: dict[tuple[str, int, int], EpubInfo] = {}
_EPUB_CACHE_MAX = 512


def read_epub_info(path: Path) -> EpubInfo:
    """Read the metadata of ``path`` (read-only; cached on path, mtime and size).

    ``ebooklib`` loads the whole archive, so the result is cached until the file
    changes.
    """
    try:
        stat = path.stat()
    except OSError as e:
        return EpubInfo(error=str(e))
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    cached = _EPUB_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        meta = EPUBMetadata(path).get_metadata()
    except Exception as e:  # noqa: BLE001 - ebooklib raises anything on bad input
        info = EpubInfo(error=str(e))
    else:
        tags = tuple(str(t) for t in meta.get("tags", []) if t)
        index = meta.get("series_index")
        info = EpubInfo(
            title=_as_text(meta.get("title")),
            author=_as_text(meta.get("author")),
            series=_as_text(meta.get("series")),
            series_index=float(index) if isinstance(index, int | float) else None,
            tags=tags,
            kind=_kind_of(tags),
            language=_as_text(meta.get("language")),
            isbn=_as_text(meta.get("isbn")),
        )
    if len(_EPUB_CACHE) >= _EPUB_CACHE_MAX:
        _EPUB_CACHE.clear()
    _EPUB_CACHE[key] = info
    return info


class VolumePreview(NamedTuple):
    """One volume as found in the destination folder.

    ``folder`` is ``None`` for an EPUB whose volume folder is gone, or for a
    volume expected from the batch but not packed yet (``planned``).
    """

    name: str
    volume: int | None
    folder: Path | None
    chapters: int
    cover: Path | None
    epub: Path | None
    epub_info: EpubInfo | None
    planned: bool = False


def _volume_number(name: str) -> int | None:
    m = _VOLUME_RE.search(name)
    return int(m.group(1)) if m else None


def _epub_stem(path: Path) -> str:
    lower = path.name.lower()
    for suffix in _EPUB_SUFFIXES:
        if lower.endswith(suffix):
            return path.name[: -len(suffix)]
    return path.stem  # pragma: no cover - list_epubs only returns *.epub


def expected_volume_names(project: Project) -> list[str]:
    """``<serie> vNN`` folder names packer will create (``[]`` when unknown)."""
    try:
        settings = resolve_packer_settings(project)
        specs = resolve_batch_specs(settings, project.source)
    except (ValueError, OSError):
        return []
    if not settings.serie:
        return []
    return [Path(format_volume_dir("", settings.serie, vol)).name for vol, _ in specs]


def volume_previews(
    dest: Path, *, expected: list[str] | None = None, read_metadata: bool = True
) -> list[VolumePreview]:
    """Volume folders and EPUBs under ``dest``, plus ``expected`` names not packed.

    Sorted by volume number (unnumbered last), then name.
    """
    previews: list[VolumePreview] = []
    seen: set[str] = set()
    for vol in list_volume_dirs(dest):
        seen.add(vol.name)
        info = read_epub_info(vol.epub) if read_metadata and vol.epub else None
        previews.append(
            VolumePreview(
                vol.name, vol.volume, vol.path, vol.chapters, vol.cover, vol.epub, info
            )
        )
    for epub_path in list_epubs(dest):
        name = _epub_stem(epub_path)
        if name in seen:
            continue
        seen.add(name)
        info = read_epub_info(epub_path) if read_metadata else None
        previews.append(
            VolumePreview(name, _volume_number(name), None, 0, None, epub_path, info)
        )
    for name in expected or []:
        if name not in seen:
            seen.add(name)
            previews.append(
                VolumePreview(
                    name, _volume_number(name), None, 0, None, None, None, True
                )
            )
    previews.sort(key=lambda v: (v.volume is None, v.volume or 0, v.name))
    return previews


def previews_summary(previews: list[VolumePreview]) -> str:
    """One-line count of folders / EPUBs / injected metadata."""
    folders = sum(1 for p in previews if p.folder is not None)
    epubs = sum(1 for p in previews if p.epub is not None)
    injected = sum(1 for p in previews if p.epub_info and p.epub_info.injected)
    planned = sum(1 for p in previews if p.planned)
    text = (
        f"{folders} volume folder(s), {epubs} EPUB(s), "
        f"{injected} with injected metadata"
    )
    return text + (f", {planned} not packed yet" if planned else "")
