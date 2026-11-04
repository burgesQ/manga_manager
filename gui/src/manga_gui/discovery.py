"""Discover series folders and per-series config files, and plan project imports.

Two existing layouts are combined into project profiles:

- a **library root** holding series folders, usually ``<root>/<LANG>/<dir>/``
  (:func:`find_series_dirs`). A folder is a series folder when it directly holds
  ``.cbz`` archives, a ``packer.json``, a ``covers/`` folder or volume folders
  named ``<Serie> vNN``;
- a **metadata dir** of files grouped by a key (:func:`find_metadata_groups`):
  ``packer_<key>.json``, ``<key>.yaml`` (metadata), ``chapters_<key>.yaml`` and
  ``vols_<key>.csv`` (batch).

:func:`plan_import` matches each group to at most one series folder (see
:class:`MatchRule` for the rules, strongest first) and returns one
:class:`ImportCandidate` per pair, per series folder without metadata and per
group without a folder. :func:`apply_import` only writes project profiles: the
user's files are never touched (``packer.json`` stays the source of truth).

Nothing here imports NiceGUI.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from collections import Counter
from enum import IntEnum
from pathlib import Path
from typing import Any, NamedTuple

from editor.editor_full import load_yaml_metadata
from packer.cli import _resolve_config_path, load_config_file

from .models import LOCALES, EditorOptions, Kind, PackerOptions, Project, slugify
from .store import Store

logger = logging.getLogger(__name__)

PACKER_JSON = "packer.json"
COVERS_DIR = "covers"
DEFAULT_LOCALE = "english"
VOLUME_DIR_RE = re.compile(r"^(?P<serie>.+?) v(?P<number>\d+)$")
"""Volume folder written by packer: ``<Serie> vNN``."""

LANG_LOCALES: dict[str, str] = {
    "en": "english",
    "eng": "english",
    "fr": "french",
    "fra": "french",
    "fre": "french",
    "ja": "japanese",
    "jp": "japanese",
    "jpn": "japanese",
}
"""Language folder name (case-insensitive) → ``editor inject --locale``."""

_YAML_SUFFIXES = (".yaml", ".yml")


# ---------------------------------------------------------------------------
# Small text helpers
# ---------------------------------------------------------------------------


def normalize(text: str) -> str:
    """Lower-case ASCII letters and digits only.

    >>> normalize("Shangri-La Frontier")
    'shangrilafrontier'
    >>> normalize("Boruto: Two Blue Vortex")
    'borutotwobluevortex'
    >>> normalize("Hajime Kōmoto")
    'hajimekomoto'
    """
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def split_words(name: str) -> list[str]:
    """Words of a folder name, split on spaces, ``-``, ``_`` and camelCase.

    >>> split_words("BorutoBlueVortex")
    ['Boruto', 'Blue', 'Vortex']
    >>> split_words("Shangri-La Frontier")
    ['Shangri', 'La', 'Frontier']
    >>> split_words("JJKM")
    ['JJKM']
    """
    words: list[str] = []
    for part in re.split(r"[\s\-_]+", name):
        words.extend(re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+", part))
    return words


def key_matches_initials(key: str, dir_name: str) -> bool:
    """True when the first key token is the first word of ``dir_name`` and the
    other tokens are the initials of the other words.

    >>> key_matches_initials("boruto_bv", "BorutoBlueVortex")
    True
    >>> key_matches_initials("boruto_b_v", "Boruto Blue Vortex")
    True
    >>> key_matches_initials("boruto", "BorutoBlueVortex")
    False
    """
    tokens = [t for t in re.split(r"[\s\-_]+", key.lower()) if t]
    words = [w.lower() for w in split_words(dir_name)]
    if len(tokens) < 2 or len(words) < 2 or tokens[0] != words[0]:
        return False
    return "".join(tokens[1:]) == "".join(w[0] for w in words[1:])


def lang_locale(lang: str | None) -> str | None:
    """Locale of a language folder name (``EN`` → ``english``), ``None`` if unknown.

    >>> [lang_locale(x) for x in ("EN", "fr", "JP", "misc", None)]
    ['english', 'french', 'japanese', None, None]
    """
    return LANG_LOCALES.get(lang.lower()) if lang else None


# ---------------------------------------------------------------------------
# Series folders
# ---------------------------------------------------------------------------


class SeriesDir(NamedTuple):
    """A series folder of the library.

    - ``label``: path relative to the library root (``EN/Zetman``);
    - ``packer_json``: its ``packer.json`` (even if invalid), else ``None``;
      ``packer_serie`` its ``serie`` when loadable;
    - ``volume_series``: ``<Serie>`` prefixes of its ``<Serie> vNN`` volume folders,
      most common first;
    - ``lang``: name of the parent folder below the root (``EN``), else ``None``.
    """

    path: Path
    label: str
    lang: str | None
    packer_json: Path | None
    packer_serie: str | None
    volume_series: tuple[str, ...]
    volume_count: int
    cbz_count: int

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def serie_names(self) -> tuple[str, ...]:
        """``packer_serie`` and ``volume_series`` (without duplicates)."""
        first = (self.packer_serie,) if self.packer_serie else ()
        return first + tuple(n for n in self.volume_series if n not in first)

    @property
    def volume_serie(self) -> str | None:
        """Most common ``<Serie>`` prefix of the volume folders."""
        return self.volume_series[0] if self.volume_series else None


def _packer_serie(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        serie = load_config_file(str(path)).get("serie")
    except ValueError:
        return None
    return serie.strip() if isinstance(serie, str) and serie.strip() else None


def _inspect_dir(path: Path, root: Path) -> SeriesDir | None:
    """A :class:`SeriesDir` when ``path`` looks like a series folder, else None."""
    try:
        entries = list(os.scandir(path))
    except OSError:
        return None
    cbz_count = 0
    has_covers = False
    packer_json: Path | None = None
    prefixes: Counter[str] = Counter()
    for entry in entries:
        try:
            is_dir = entry.is_dir()
        except OSError:  # pragma: no cover - broken entry
            continue
        if is_dir:
            if entry.name == COVERS_DIR:
                has_covers = True
            elif m := VOLUME_DIR_RE.match(entry.name):
                prefixes[m.group("serie").strip()] += 1
        elif entry.name.lower().endswith(".cbz"):
            cbz_count += 1
        elif entry.name == PACKER_JSON:
            packer_json = path / PACKER_JSON
    if not (cbz_count or has_covers or packer_json or prefixes):
        return None
    rel = path.relative_to(root)
    return SeriesDir(
        path=path,
        label=rel.as_posix() if rel.parts else path.name,
        lang=rel.parts[-2] if len(rel.parts) >= 2 else None,
        packer_json=packer_json,
        packer_serie=_packer_serie(packer_json),
        volume_series=tuple(n for n, _ in prefixes.most_common()),
        volume_count=sum(prefixes.values()),
        cbz_count=cbz_count,
    )


def _sub_dirs(path: Path) -> list[Path]:
    try:
        return sorted(
            Path(e.path)
            for e in os.scandir(path)
            if e.is_dir() and not e.name.startswith(".")
        )
    except OSError as e:
        logger.debug("cannot list %s: %s", path, e)
        return []


def find_series_dirs(library_root: Path, *, max_depth: int = 2) -> list[SeriesDir]:
    """Series folders under ``library_root`` (at most ``max_depth`` levels down).

    Series folders are not descended into, nor are hidden folders and git
    repositories (a folder holding ``.git``). The root itself counts when it is a
    series folder. Sorted by ``label``.
    """
    root = Path(library_root)
    if not root.is_dir():
        return []
    itself = _inspect_dir(root, root)
    if itself is not None:
        return [itself]
    found: list[SeriesDir] = []

    def walk(path: Path, depth: int) -> None:
        for child in _sub_dirs(path):
            series = _inspect_dir(child, root)
            if series is not None:
                found.append(series)
            elif depth < max_depth and not (child / ".git").exists():
                walk(child, depth + 1)

    walk(root, 1)
    return sorted(found, key=lambda s: s.label.lower())


# ---------------------------------------------------------------------------
# Metadata groups
# ---------------------------------------------------------------------------


class MetadataGroup(NamedTuple):
    """Files of one key in the metadata dir (each one optional)."""

    key: str
    packer_json: Path | None = None
    metadata_yaml: Path | None = None
    chapters_yaml: Path | None = None
    batch_csv: Path | None = None

    @property
    def files(self) -> list[Path]:
        return [
            p
            for p in (
                self.packer_json,
                self.metadata_yaml,
                self.chapters_yaml,
                self.batch_csv,
            )
            if p is not None
        ]


def _classify(path: Path) -> tuple[str, str] | None:
    """``(field, key)`` of a metadata dir file, ``None`` when it is not one.

    >>> [_classify(Path(n)) for n in ("packer_fma.json", "chapters_jjk.yaml")]
    [('packer_json', 'fma'), ('chapters_yaml', 'jjk')]
    >>> [_classify(Path(n)) for n in ("vols_jjk.csv", "mashle.yml", "notes.txt")]
    [('batch_csv', 'jjk'), ('metadata_yaml', 'mashle'), None]
    """
    stem, suffix = path.stem, path.suffix.lower()
    if suffix == ".json" and stem.startswith("packer_"):
        return "packer_json", stem.removeprefix("packer_")
    if suffix == ".csv" and stem.startswith("vols_"):
        return "batch_csv", stem.removeprefix("vols_")
    if suffix in _YAML_SUFFIXES:
        if stem.startswith("chapters_"):
            return "chapters_yaml", stem.removeprefix("chapters_")
        return "metadata_yaml", stem
    return None


def find_metadata_groups(metadata_dir: Path) -> list[MetadataGroup]:
    """Group the files of ``metadata_dir`` by key, sorted by key."""
    directory = Path(metadata_dir)
    if not directory.is_dir():
        return []
    fields: dict[str, dict[str, Path]] = {}
    for path in sorted(directory.iterdir()):
        if path.name.startswith(".") or not path.is_file():
            continue
        found = _classify(path)
        if found is None or not found[1]:
            continue
        field, key = found
        fields.setdefault(key, {}).setdefault(field, path)
    return [MetadataGroup(key, **fields[key]) for key in sorted(fields)]


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


class MatchRule(IntEnum):
    """How a metadata group was matched to a series folder (strongest first)."""

    COVERS = 1
    """the covers of ``packer_<key>.json`` lie inside the folder"""
    SERIE = 2
    """``serie`` / ``series`` equals a serie name of the folder"""
    KEY = 3
    """the key equals the folder name"""
    INITIALS = 4
    """the key is the first word + the initials of the other words"""
    PREFIX = 5
    """the folder name starts with the key"""


class _GroupData(NamedTuple):
    """A group with its files loaded (``None`` + error when unreadable)."""

    group: MetadataGroup
    packer: dict[str, Any] | None
    packer_error: str | None
    metadata: dict[str, Any] | None
    metadata_error: str | None

    @property
    def names(self) -> list[str]:
        out = []
        for data, key in ((self.packer, "serie"), (self.metadata, "series")):
            value = (data or {}).get(key)
            if isinstance(value, str) and value.strip():
                out.append(value.strip())
        return out


def _load_packer(path: Path | None) -> tuple[dict[str, Any] | None, str | None]:
    if path is None:
        return None, None
    try:
        return load_config_file(str(path), required=True), None
    except ValueError as e:
        return None, str(e)


def _load_metadata(path: Path | None) -> tuple[dict[str, Any] | None, str | None]:
    if path is None:
        return None, None
    try:
        data = load_yaml_metadata(path)
    except Exception as e:  # yaml.YAMLError, OSError, UnicodeDecodeError …
        return None, f"invalid metadata YAML ({path.name}): {e}"
    if not isinstance(data, dict):
        return None, f"invalid metadata YAML ({path.name}): not a mapping"
    return data, None


def _load_group(group: MetadataGroup) -> _GroupData:
    packer, packer_error = _load_packer(group.packer_json)
    metadata, metadata_error = _load_metadata(group.metadata_yaml)
    return _GroupData(group, packer, packer_error, metadata, metadata_error)


def _cover_paths(data: _GroupData) -> list[Path]:
    covers = (data.packer or {}).get("covers")
    if not isinstance(covers, dict) or data.group.packer_json is None:
        return []
    base = str(data.group.packer_json.parent)
    return [
        Path(_resolve_config_path(str(value), base))
        for value in covers.values()
        if isinstance(value, str) and value.strip()
    ]


def _match(data: _GroupData, series: SeriesDir) -> tuple[MatchRule, str] | None:
    """The strongest rule matching ``data`` to ``series`` and its reason."""
    group = data.group
    if any(p.is_relative_to(series.path) for p in _cover_paths(data)):
        assert group.packer_json is not None
        return MatchRule.COVERS, (
            f"covers of {group.packer_json.name} are in {series.label}"
        )
    dir_names = {normalize(n): n for n in series.serie_names}
    for name in data.names:
        if normalize(name) in dir_names:
            return MatchRule.SERIE, f"serie {name!r} matches {series.label}"
    key, dir_name = normalize(group.key), normalize(series.name)
    if key and key == dir_name:
        return MatchRule.KEY, f"key {group.key!r} matches folder {series.name!r}"
    if key_matches_initials(group.key, series.name):
        return MatchRule.INITIALS, (
            f"key {group.key!r} matches the initials of {series.name!r}"
        )
    if len(key) >= 3 and dir_name.startswith(key):
        return MatchRule.PREFIX, f"folder {series.name!r} starts with {group.key!r}"
    return None


def match_groups(
    groups: list[_GroupData], series_dirs: list[SeriesDir]
) -> dict[str, tuple[SeriesDir, str]]:
    """``{key: (series folder, reason)}``: one folder per group at most.

    Every (group, folder) pair is scored and the pairs are taken strongest first,
    so an exact match wins over a looser one (``boruto`` gets ``Boruto``, not
    ``BorutoBlueVortex``). Ties prefer the folder name closest in length to the key.
    """
    pairs: list[tuple[tuple[int, int, str, str], _GroupData, SeriesDir, str]] = []
    for data in groups:
        for series in series_dirs:
            found = _match(data, series)
            if found is None:
                continue
            rule, reason = found
            closeness = abs(len(normalize(series.name)) - len(data.group.key))
            sort_key = (int(rule), closeness, data.group.key, series.label)
            pairs.append((sort_key, data, series, reason))
    matched: dict[str, tuple[SeriesDir, str]] = {}
    used: set[Path] = set()
    for _, data, series, reason in sorted(pairs, key=lambda p: p[0]):
        if data.group.key in matched or series.path in used:
            continue
        matched[data.group.key] = (series, reason)
        used.add(series.path)
    return matched


# ---------------------------------------------------------------------------
# Import plan
# ---------------------------------------------------------------------------


class ImportCandidate(NamedTuple):
    """A project that can be created from a series folder and / or a group.

    ``source`` is ``None`` for a group without series folder: it cannot be
    imported (``importable`` is False). ``issues`` are warnings (invalid
    ``packer.json`` or YAML …), they do not block the import.
    """

    name: str
    slug: str
    kind: Kind
    source: Path | None
    packer_config: Path | None
    metadata: Path | None
    chapters: Path | None
    locale: str
    reason: str
    issues: tuple[str, ...]
    exists: bool
    key: str | None = None
    label: str | None = None
    batch_csv: Path | None = None

    @property
    def importable(self) -> bool:
        return self.source is not None

    @property
    def files(self) -> list[str]:
        """Names of the config files the project points to (+ the batch CSV);
        ``./name`` for a file inside the source folder."""
        paths = (self.packer_config, self.metadata, self.chapters, self.batch_csv)
        return [
            (
                f"./{p.name}"
                if self.source is not None and p.parent == self.source
                else p.name
            )
            for p in paths
            if p is not None
        ]

    def status(self, *, overwrite: bool = False) -> str:
        """``new``, ``exists`` (skipped), ``overwrite`` or ``no source``."""
        if not self.importable:
            return "no source"
        if self.exists:
            return "overwrite" if overwrite else "exists"
        return "new"


def _yaml_locale(metadata: dict[str, Any] | None) -> str | None:
    """Most used locale block of the YAML volumes (ties: :data:`LOCALES` order)."""
    volumes = (metadata or {}).get("volumes")
    if not isinstance(volumes, list):
        return None
    counts = Counter(
        loc for vol in volumes if isinstance(vol, dict) for loc in LOCALES if loc in vol
    )
    if not counts:
        return None
    return max(LOCALES, key=lambda loc: (counts[loc], -LOCALES.index(loc)))


def _locale_issue(metadata: dict[str, Any] | None, locale: str) -> str | None:
    volumes = (metadata or {}).get("volumes")
    if not isinstance(volumes, list) or not volumes:
        return None
    if any(isinstance(v, dict) and locale in v for v in volumes):
        return None
    return f"metadata YAML volumes have no `{locale}` block"


def _candidate(
    data: _GroupData | None,
    series: SeriesDir | None,
    reason: str,
    store: Store,
) -> ImportCandidate:
    group = data.group if data is not None else None
    issues: list[str] = []

    # packer config: the group's file, else the folder's packer.json
    packer_config: Path | None = None
    packer: dict[str, Any] | None = None
    if data is not None and group is not None and group.packer_json is not None:
        packer_config, packer = group.packer_json, data.packer
        if data.packer_error:
            issues.append(data.packer_error)
            if series is not None and series.packer_json is not None:
                own, own_error = _load_packer(series.packer_json)
                if own is not None:
                    issues.append(f"using {series.label}/{PACKER_JSON} instead")
                    packer_config, packer = series.packer_json, own
    elif series is not None and series.packer_json is not None:
        packer_config = series.packer_json
        packer, error = _load_packer(series.packer_json)
        if error:
            issues.append(error)

    metadata = data.metadata if data is not None else None
    if data is not None and data.metadata_error:
        issues.append(data.metadata_error)

    # name: packer serie, yaml series, volume folders, folder name, key
    candidates_names: list[Any] = [
        (packer or {}).get("serie"),
        (metadata or {}).get("series"),
        series.volume_serie if series is not None else None,
        series.name if series is not None else None,
        group.key if group is not None else None,
    ]
    name = next(n.strip() for n in candidates_names if isinstance(n, str) and n.strip())

    kind_value = (packer or {}).get("kind")
    kind = Kind(kind_value) if kind_value in {k.value for k in Kind} else Kind.MANGA

    chapters = group.chapters_yaml if group is not None else None
    if chapters is not None and (metadata or {}).get("chapters_file"):
        chapters = None  # the metadata YAML already points to it

    locale = (
        lang_locale(series.lang if series is not None else None)
        or _yaml_locale(metadata)
        or DEFAULT_LOCALE
    )
    if group is not None and group.metadata_yaml is not None:
        if (problem := _locale_issue(metadata, locale)) is not None:
            issues.append(problem)

    slug = slugify(name)
    return ImportCandidate(
        name=name,
        slug=slug,
        kind=kind,
        source=series.path if series is not None else None,
        packer_config=packer_config,
        metadata=group.metadata_yaml if group is not None else None,
        chapters=chapters,
        locale=locale,
        reason=reason,
        issues=tuple(issues),
        exists=store.has_project(slug),
        key=group.key if group is not None else None,
        label=series.label if series is not None else None,
        batch_csv=group.batch_csv if group is not None else None,
    )


def _dedupe_slugs(
    candidates: list[ImportCandidate], store: Store
) -> list[ImportCandidate]:
    """Rename candidates sharing a slug (``Name (EN)``, then ``Name (2)`` …)."""
    seen: set[str] = set()
    out: list[ImportCandidate] = []
    for cand in candidates:
        if cand.slug in seen:
            lang = cand.label.split("/")[0] if cand.label and "/" in cand.label else ""
            options = [f"{cand.name} ({lang})"] if lang else []
            options += [f"{cand.name} ({n})" for n in range(2, 100)]
            name = next(n for n in options if slugify(n) not in seen)
            slug = slugify(name)
            cand = cand._replace(name=name, slug=slug, exists=store.has_project(slug))
        seen.add(cand.slug)
        out.append(cand)
    return out


def plan_import(
    metadata_dir: Path | None, library_root: Path | None, store: Store
) -> list[ImportCandidate]:
    """One candidate per matched (group, series folder) pair, per series folder
    without metadata and per group without folder (not importable).

    Importable candidates come first, each part sorted by name. Reads files only.
    """
    groups = [
        _load_group(g)
        for g in (find_metadata_groups(metadata_dir) if metadata_dir else [])
    ]
    series_dirs = find_series_dirs(library_root) if library_root else []
    matched = match_groups(groups, series_dirs)
    used = {series.path for series, _ in matched.values()}

    candidates: list[ImportCandidate] = []
    for data in groups:
        if data.group.key in matched:
            series, reason = matched[data.group.key]
            candidates.append(_candidate(data, series, reason, store))
    for series in series_dirs:
        if series.path not in used:
            reason = "series folder without metadata files"
            candidates.append(_candidate(None, series, reason, store))
    orphans = [
        _candidate(data, None, "no matching series folder", store)
        for data in groups
        if data.group.key not in matched
    ]
    candidates.sort(key=lambda c: (c.name.lower(), c.label or ""))
    orphans.sort(key=lambda c: c.name.lower())
    return _dedupe_slugs(candidates + orphans, store)


def candidate_for_source(
    source: Path, metadata_dir: Path | None, library_root: Path | None, store: Store
) -> ImportCandidate | None:
    """The importable candidate of the series folder ``source`` (if any)."""
    for cand in plan_import(metadata_dir, library_root, store):
        if cand.source == source:
            return cand
    return None


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def apply_candidate(project: Project, candidate: ImportCandidate) -> Project:
    """Point ``project`` to the candidate's config files (in place, returned).

    Only ``packer.config`` and the editor files / locale are set: other options
    keep their values, the files stay the source of truth. When the packer config
    changes, ``serie`` / ``pattern`` copied from another ``packer.json`` are reset.
    """
    opts = project.packer
    if candidate.packer_config is not None and candidate.packer_config != opts.config:
        opts.config = candidate.packer_config
        opts.serie = None
        opts.pattern = PackerOptions().pattern
    project.editor.metadata = candidate.metadata
    project.editor.chapters = candidate.chapters
    project.editor.locale = candidate.locale
    return project


def build_project(candidate: ImportCandidate) -> Project:
    """The :class:`Project` of an importable candidate."""
    if candidate.source is None:
        raise ValueError(f"{candidate.name}: no source folder")
    project = Project(
        name=candidate.name,
        slug=candidate.slug,
        kind=candidate.kind,
        source=candidate.source,
        packer=PackerOptions(),
        editor=EditorOptions(),
    )
    return apply_candidate(project, candidate)


class ImportReport(NamedTuple):
    """Slugs created, overwritten, skipped (already existing) and failures."""

    created: list[str]
    overwritten: list[str]
    skipped: list[str]
    failed: list[tuple[str, str]]

    def summary(self) -> str:
        """``"2 created, 0 overwritten, 1 skipped (exists), 0 failed"``."""
        return (
            f"{len(self.created)} created, {len(self.overwritten)} overwritten, "
            f"{len(self.skipped)} skipped (exists), {len(self.failed)} failed"
        )


def apply_import(
    candidates: list[ImportCandidate], store: Store, *, overwrite: bool = False
) -> ImportReport:
    """Save one project per candidate. Existing slugs are skipped unless
    ``overwrite``; non-importable candidates fail. Only profiles are written.
    """
    report = ImportReport([], [], [], [])
    for cand in candidates:
        try:
            project = build_project(cand)
            exists = store.has_project(project.slug)
            if exists and not overwrite:
                report.skipped.append(project.slug)
                continue
            store.save_project(project)
        except (OSError, ValueError) as e:
            logger.warning("not imported %s: %s", cand.name, e)
            report.failed.append((cand.slug, str(e)))
            continue
        (report.overwritten if exists else report.created).append(project.slug)
        logger.info("imported project %s (%s)", project.slug, project.source)
    return report


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

PLAN_COLUMNS = ("status", "name", "source", "files", "reason", "issues")


def describe_candidate(candidate: ImportCandidate) -> list[str]:
    """Lines describing what a candidate prefills (New project form)."""
    lines = [f"Library: {candidate.reason}"]
    for label, path in (
        ("packer config", candidate.packer_config),
        ("metadata", candidate.metadata),
        ("chapters", candidate.chapters),
    ):
        if path is not None:
            lines.append(f"{label}: {path}")
    lines.append(f"locale: {candidate.locale}")
    lines.extend(f"Warning: {issue}" for issue in candidate.issues)
    return lines


def plan_rows(
    candidates: list[ImportCandidate], *, overwrite: bool = False
) -> list[tuple[str, ...]]:
    """One display row per candidate (see :data:`PLAN_COLUMNS`)."""
    return [
        (
            c.status(overwrite=overwrite),
            c.name,
            c.label or "-",
            ", ".join(c.files) or "-",
            c.reason,
            "; ".join(c.issues) or "-",
        )
        for c in candidates
    ]


def format_plan(
    candidates: list[ImportCandidate], *, overwrite: bool = False
) -> list[str]:
    """The plan as aligned text lines (a header then one line per candidate).

    The last column (issues) is not padded.
    """
    rows = [PLAN_COLUMNS, *plan_rows(candidates, overwrite=overwrite)]
    widths = [max(len(r[i]) for r in rows) for i in range(len(PLAN_COLUMNS) - 1)]
    return [
        "  ".join(
            [
                *(cell.ljust(w) for cell, w in zip(row[:-1], widths, strict=True)),
                row[-1],
            ]
        ).rstrip()
        for row in rows
    ]
