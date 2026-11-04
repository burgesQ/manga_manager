"""UI-free helpers behind the wizard forms.

Everything the project page needs that is not widget code lives here so it can be
unit-tested without NiceGUI:

- batch table rows ↔ batch CSV text / batch spec (``packer.cli.parse_batch_file``
  and ``parse_batch_spec`` formats);
- volume-mode switching of :class:`~manga_gui.models.PackerOptions`;
- ``packer.json`` edits (raw text save validated by ``load_config_file``, ``kind``
  and ``covers`` updates that keep the other keys);
- KCC effective values (convertor preset + explicit overrides);
- metadata YAML → series fields / volume rows / chapter-title rows, and the raw
  YAML save validated by ``editor.editor_full.load_yaml_metadata``;
- per-step run status.

Config files are written atomically (temp file in the same folder, then
``replace``) and validated by the CLI loaders before they replace the real file.
"""

from __future__ import annotations

import json
import os
import re
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, NamedTuple

import yaml

from convertor.kcc_adapter import PRESETS, KCCSettings
from editor.editor_full import _resolve_chapter_titles, load_yaml_metadata
from packer.cli import _resolve_config_path, load_config_file
from packer.core import parse_range

from .models import KCCOptions, Kind, PackerOptions, Project
from .runner import StepResult
from .scan import ScanResult
from .validation import resolve_packer_settings

# ---------------------------------------------------------------------------
# Small parsing helpers
# ---------------------------------------------------------------------------


def parse_path(text: str | None) -> Path | None:
    """Path typed in a form field: blank → ``None``, ``~`` expanded.

    >>> parse_path("  ") is None
    True
    >>> parse_path("/srv/manga")
    PosixPath('/srv/manga')
    """
    if text is None or not text.strip():
        return None
    return Path(text.strip()).expanduser()


def parse_optional_text(text: str | None) -> str | None:
    """Text typed in a form field: blank → ``None`` (surrounding spaces kept).

    >>> parse_optional_text("") is None
    True
    >>> parse_optional_text("Berserk")
    'Berserk'
    """
    if text is None or not text.strip():
        return None
    return text


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _validated_write(path: Path, text: str, check: Any) -> None:
    """Write ``text`` to a temp sibling, run ``check(tmp)``, then replace ``path``.

    ``check`` raises to reject the content; the temp file is removed and the real
    file is left untouched in that case.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        check(tmp)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Batch table
# ---------------------------------------------------------------------------


class BatchRow(NamedTuple):
    """One volume of the batch table: ``chapters`` is a packer range string."""

    volume: int
    chapters: str


_BATCH_VOL_RE = re.compile(r"(?i)v?\s*0*([0-9]+)")
_SPEC_RE = re.compile(r"(?i)v\s*0*([0-9]+):(.+)")


def validate_batch_rows(rows: list[BatchRow]) -> list[str]:
    """Return human-readable problems of ``rows`` (empty list = valid).

    >>> validate_batch_rows([BatchRow(1, "1..3"), BatchRow(1, "x")])
    ["volume 1: invalid range 'x'", 'volume 1 listed more than once']
    """
    problems: list[str] = []
    seen: set[int] = set()
    for row in rows:
        if row.volume < 0:
            problems.append(f"volume {row.volume}: must be >= 0")
        try:
            if not parse_range(row.chapters):
                raise ValueError
        except (ValueError, TypeError):
            problems.append(f"volume {row.volume}: invalid range {row.chapters!r}")
        if row.volume in seen:
            problems.append(f"volume {row.volume} listed more than once")
        seen.add(row.volume)
    return problems


def batch_rows_from_text(text: str) -> list[BatchRow]:
    """Parse batch CSV text (``vNN,range`` lines) like ``parse_batch_file``.

    Blank lines and ``#`` comments are skipped; the range is kept verbatim.
    Raises ``ValueError`` on a malformed line.

    >>> batch_rows_from_text("# vols\\nv1,1..12\\n2, 13..26\\n")
    [BatchRow(volume=1, chapters='1..12'), BatchRow(volume=2, chapters='13..26')]
    """
    rows: list[BatchRow] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) < 2:
            raise ValueError(f"invalid batch file line: {line}")
        m = _BATCH_VOL_RE.match(parts[0])
        if not m:
            raise ValueError(f"invalid volume spec in batch file: {parts[0]}")
        # parse_batch_file only reads parts[1]: "1,3,5" ranges are not supported
        # in the CSV, so keep the second field exactly like packer does.
        rows.append(BatchRow(int(m.group(1)), parts[1]))
    return rows


def batch_rows_to_text(rows: list[BatchRow]) -> str:
    """Render ``rows`` as batch CSV text readable by ``parse_batch_file``.

    Raises ``ValueError`` when a row is invalid or a range contains a comma
    (the CSV format only keeps the first range field).

    >>> print(batch_rows_to_text([BatchRow(1, "1..12"), BatchRow(2, "13..26")]))
    v01,1..12
    v02,13..26
    <BLANKLINE>
    """
    problems = validate_batch_rows(rows)
    problems += [
        f"volume {r.volume}: ',' is not allowed in a batch file range"
        for r in rows
        if "," in r.chapters
    ]
    if problems:
        raise ValueError("; ".join(problems))
    return "".join(f"v{r.volume:02d},{r.chapters.strip()}\n" for r in rows)


def batch_rows_from_spec(spec: str | None) -> list[BatchRow]:
    """Parse a ``--batch`` spec (``v01:1..3-v02:4..6``) into rows.

    >>> batch_rows_from_spec("v01:1..3-v02:4,6")
    [BatchRow(volume=1, chapters='1..3'), BatchRow(volume=2, chapters='4,6')]
    """
    rows: list[BatchRow] = []
    for part in (spec or "").split("-"):
        if not part.strip():
            continue
        m = _SPEC_RE.match(part.strip())
        if not m:
            raise ValueError(f"invalid batch spec: {part}")
        rows.append(BatchRow(int(m.group(1)), m.group(2).strip()))
    return rows


def batch_rows_to_spec(rows: list[BatchRow]) -> str:
    """Render ``rows`` as a ``--batch`` spec readable by ``parse_batch_spec``.

    >>> batch_rows_to_spec([BatchRow(1, "1..3"), BatchRow(2, "4..6")])
    'v01:1..3-v02:4..6'
    """
    problems = validate_batch_rows(rows)
    if problems:
        raise ValueError("; ".join(problems))
    return "-".join(f"v{r.volume:02d}:{r.chapters.strip()}" for r in rows)


def read_batch_file(path: Path) -> list[BatchRow]:
    """Rows of the batch CSV at ``path`` (``[]`` when it does not exist)."""
    if not path.is_file():
        return []
    return batch_rows_from_text(path.read_text(encoding="utf-8"))


def write_batch_file(path: Path, rows: list[BatchRow]) -> None:
    """Write ``rows`` to ``path`` as batch CSV (validated, atomic)."""
    _write_atomic(path, batch_rows_to_text(rows))


def effective_batch_file(project: Project) -> Path:
    """Batch CSV the "batch file" mode edits.

    The project's ``batch_file``, else ``batch_file`` from ``packer.json``
    (resolved like packer does), else ``<source>/.batch`` (auto-discovered by
    packer).
    """
    if project.packer.batch_file is not None:
        return project.packer.batch_file
    try:
        settings = resolve_packer_settings(project)
    except ValueError:
        settings = None
    if settings is not None and settings.batch_file is not None:
        return settings.batch_file
    return project.source / ".batch"


# ---------------------------------------------------------------------------
# Volume mode
# ---------------------------------------------------------------------------

VolumeMode = Literal["spec", "file", "single"]
VOLUME_MODES: dict[str, str] = {
    "spec": "Batch spec",
    "file": "Batch file",
    "single": "Single volume",
}
_MODE_FIELDS: dict[str, tuple[str, ...]] = {
    "spec": ("batch",),
    "file": ("batch_file",),
    "single": ("volume", "chapter_range"),
}


def volume_mode(opts: PackerOptions) -> VolumeMode:
    """Mode matching the options set (same precedence as packer).

    >>> volume_mode(PackerOptions(batch="v01:1"))
    'spec'
    >>> volume_mode(PackerOptions(volume=1, chapter_range="1..3"))
    'single'
    >>> volume_mode(PackerOptions())
    'file'
    """
    if opts.batch:
        return "spec"
    if opts.batch_file is None and (
        opts.volume is not None or opts.chapter_range is not None
    ):
        return "single"
    return "file"


def switch_volume_mode(
    opts: PackerOptions, new_mode: VolumeMode, stash: dict[str, Any]
) -> None:
    """Clear the fields of the other modes, keeping them in ``stash``.

    The fields not used by ``new_mode`` are moved into ``stash`` and the fields
    of ``new_mode`` are restored from it, so toggling back and forth in the UI
    loses nothing while the saved options never mix modes (packer rejects
    ``--batch`` combined with ``--volume``).
    """
    for mode, names in _MODE_FIELDS.items():
        for name in names:
            if mode == new_mode:
                if getattr(opts, name) is None and name in stash:
                    setattr(opts, name, stash.pop(name))
            else:
                value = getattr(opts, name)
                if value is not None:
                    stash[name] = value
                setattr(opts, name, None)


# ---------------------------------------------------------------------------
# packer.json
# ---------------------------------------------------------------------------

PACKER_JSON_TEMPLATE = "{\n}\n"


def dump_packer_json(data: dict[str, Any]) -> str:
    """``packer.json`` text as the GUI writes it (``indent=2``, trailing newline)."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def read_text_or(path: Path | None, default: str) -> str:
    """Text of ``path``, or ``default`` when unset / missing."""
    if path is None or not path.is_file():
        return default
    return path.read_text(encoding="utf-8")


def save_packer_json_text(path: Path, text: str) -> dict[str, Any]:
    """Validate ``text`` with ``load_config_file`` then write it to ``path``.

    Returns the parsed config. Raises ``ValueError`` (the real file is left
    untouched) when the JSON is invalid for packer.
    """
    result: dict[str, Any] = {}

    def _check(tmp: Path) -> None:
        result.update(load_config_file(str(tmp), required=True))

    _validated_write(path, text, _check)
    return result


def _load_packer_json(path: Path) -> dict[str, Any]:
    return load_config_file(str(path), required=False)


def set_packer_json_kind(path: Path, kind: Kind) -> bool:
    """Write ``kind`` into an *existing* ``packer.json``, keeping other keys.

    Returns True when the file was changed; False when it does not exist or
    already holds ``kind``. Raises ``ValueError`` on an invalid file.
    """
    if not path.is_file():
        return False
    data = _load_packer_json(path)
    if data.get("kind") == kind.value:
        return False
    data["kind"] = kind.value
    _write_atomic(path, dump_packer_json(data))
    return True


def packer_json_covers(path: Path) -> dict[int, str]:
    """Raw ``covers`` entries of ``packer.json`` (volume → path as written)."""
    try:
        data = _load_packer_json(path)
    except ValueError:
        return {}
    raw = data.get("covers")
    covers: dict[int, str] = {}
    if isinstance(raw, dict):
        for vol, cover in raw.items():
            try:
                covers[int(vol)] = str(cover)
            except (TypeError, ValueError):
                continue
    return covers


def set_packer_json_covers(path: Path, covers: dict[int, str]) -> None:
    """Replace ``covers`` in ``packer.json`` (created if missing), keeping others.

    Blank entries are dropped; an empty mapping removes the ``covers`` key.
    Keys are written as strings sorted by volume, like the hand-written files.
    """
    data = _load_packer_json(path) if path.is_file() else {}
    cleaned = {vol: c.strip() for vol, c in covers.items() if c and c.strip()}
    if cleaned:
        data["covers"] = {str(vol): cleaned[vol] for vol in sorted(cleaned)}
    else:
        data.pop("covers", None)
    _write_atomic(path, dump_packer_json(data))


class CoverRow(NamedTuple):
    """One cell of the covers grid."""

    volume: int
    raw: str
    resolved: Path | None

    @property
    def exists(self) -> bool:
        return self.resolved is not None and self.resolved.is_file()


def resolve_cover(raw: str, config_path: Path) -> Path | None:
    """Resolve a ``covers`` entry like packer (relative to the config folder)."""
    if not raw.strip():
        return None
    base_dir = str(config_path.expanduser().absolute().parent)
    return Path(_resolve_config_path(raw.strip(), base_dir))


def cover_rows(
    config_path: Path, volumes: list[int], covers: dict[int, str]
) -> list[CoverRow]:
    """One row per volume of the batch plus every volume that has a cover."""
    rows: list[CoverRow] = []
    for vol in sorted(set(volumes) | set(covers)):
        raw = covers.get(vol, "")
        rows.append(CoverRow(vol, raw, resolve_cover(raw, config_path)))
    return rows


# ---------------------------------------------------------------------------
# KCC (convertor)
# ---------------------------------------------------------------------------

KCC_BOOL_FIELDS: tuple[tuple[str, str], ...] = (
    ("manga_style", "Manga style (right-to-left)"),
    ("hq", "High quality"),
    ("forcecolor", "Force colour"),
    ("upscale", "Upscale"),
    ("blackborders", "Black borders"),
)
"""Boolean KCC overrides shown as tri-state toggles: (field, label)."""

TriState = Literal["inherit", "on", "off"]
TRI_STATES: dict[str, str] = {"inherit": "Inherit", "on": "On", "off": "Off"}


def tri_state(value: bool | None) -> TriState:
    """``None`` → ``inherit``, ``True`` → ``on``, ``False`` → ``off``."""
    if value is None:
        return "inherit"
    return "on" if value else "off"


def from_tri_state(state: str | None) -> bool | None:
    """Inverse of :func:`tri_state` (anything unknown → ``None``)."""
    if state == "on":
        return True
    if state == "off":
        return False
    return None


def kcc_preset(kind: Kind) -> KCCSettings:
    """The convertor preset selected by ``--preset <kind>``."""
    return PRESETS[kind.value]


def effective_kcc(kind: Kind, opts: KCCOptions) -> KCCSettings:
    """KCC settings convertor will use: the preset with the explicit overrides.

    >>> effective_kcc(Kind.COMIC, KCCOptions()).manga_style
    False
    >>> effective_kcc(Kind.COMIC, KCCOptions(manga_style=True)).manga_style
    True
    """
    overrides = {
        name: getattr(opts, name)
        for name in KCCSettings._fields
        if getattr(opts, name, None) is not None
    }
    return kcc_preset(kind)._replace(**overrides)


def reading_direction(settings: KCCSettings) -> str:
    """Human label of the page progression KCC will write."""
    if settings.manga_style:
        return "Right-to-left (manga)"
    return "Left-to-right (comic)"


def format_kcc_value(value: Any) -> str:
    """Display form of a KCC value (``on`` / ``off`` for booleans)."""
    if isinstance(value, bool):
        return "on" if value else "off"
    return str(value)


# ---------------------------------------------------------------------------
# Metadata YAML
# ---------------------------------------------------------------------------

SERIES_FIELDS: tuple[str, ...] = (
    "series",
    "author",
    "publisher",
    "language",
    "kind",
    "genre",
)
"""Top-level metadata keys shown in the series form."""

METADATA_TEMPLATE = 'series: ""\nauthor: ""\nvolumes: []\n'


def dump_yaml(data: Any) -> str:
    """YAML text as the GUI writes it (key order and unicode preserved)."""
    return str(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def parse_metadata_text(text: str) -> dict[str, Any]:
    """Parse metadata YAML text; raises ``ValueError`` unless it is a mapping."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f"invalid YAML: {e}") from e
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("metadata YAML must be a mapping at top level")
    return data


def _check_metadata(data: Any) -> None:
    if not isinstance(data, dict):
        raise ValueError("metadata YAML must be a mapping at top level")
    kind = data.get("kind")
    if kind is not None and kind not in {k.value for k in Kind}:
        raise ValueError(f"kind must be one of manga, comic (got {kind!r})")
    volumes = data.get("volumes")
    if volumes is not None and not isinstance(volumes, list):
        raise ValueError("`volumes` must be a list")
    for vol in volumes or []:
        if not isinstance(vol, dict) or "number" not in vol:
            raise ValueError("every volume needs a `number`")


def save_metadata_text(path: Path, text: str) -> dict[str, Any]:
    """Validate ``text`` with ``load_yaml_metadata`` then write it to ``path``.

    The text is written verbatim (comments are kept). Returns the parsed data;
    raises ``ValueError`` and leaves the real file untouched when invalid.
    """
    result: dict[str, Any] = {}

    def _check(tmp: Path) -> None:
        try:
            data = load_yaml_metadata(tmp)
        except yaml.YAMLError as e:
            raise ValueError(f"invalid YAML: {e}") from e
        _check_metadata(data)
        result.update(data)

    _validated_write(path, text, _check)
    return result


def _display(value: Any, locale: str) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return str(value.get(locale, ""))
    return str(value)


def series_fields(data: dict[str, Any], locale: str) -> dict[str, str]:
    """Display strings of :data:`SERIES_FIELDS`.

    Lists are joined with ``", "``; a per-locale mapping (``publisher``) shows
    the ``locale`` entry.

    >>> series_fields({"series": "X", "genre": ["A", "B"],
    ...                "publisher": {"english": "Viz"}}, "english")["genre"]
    'A, B'
    """
    return {key: _display(data.get(key), locale) for key in SERIES_FIELDS}


def apply_series_fields(
    data: dict[str, Any], new_fields: dict[str, str], locale: str
) -> dict[str, Any]:
    """Return a copy of ``data`` with the *changed* series fields applied.

    Unchanged fields keep their original structure (lists, per-locale
    mappings). A blank field removes the key. ``genre`` and a list ``author``
    are split on commas; a mapping ``publisher`` gets its ``locale`` entry set.
    New keys are inserted before ``volumes`` so the file stays readable.
    """
    current = series_fields(data, locale)
    changed: dict[str, Any] = {}
    for key in SERIES_FIELDS:
        if key not in new_fields or new_fields[key] == current[key]:
            continue
        text = new_fields[key].strip()
        old = data.get(key)
        value: Any
        if key == "genre" or (key == "author" and isinstance(old, list)):
            value = [p.strip() for p in text.split(",") if p.strip()]
        elif key == "publisher" and isinstance(old, dict):
            value = {k: v for k, v in old.items() if k != locale}
            if text:
                value[locale] = text
        else:
            value = text
        changed[key] = value

    out: dict[str, Any] = {}
    added = [k for k in changed if k not in data]
    for key, value in data.items():
        if key == "volumes":  # new series keys go before the volumes list
            out.update({k: changed[k] for k in added})
            added = []
        out[key] = changed.get(key, value)
    out.update({k: changed[k] for k in added})
    return {k: v for k, v in out.items() if k not in changed or v not in ("", [], {})}


class VolumeRow(NamedTuple):
    number: Any
    title: str
    isbn: str
    release_date: str


def volume_rows(data: dict[str, Any], locale: str) -> list[VolumeRow]:
    """Volumes of the metadata with the ``locale`` ISBN / release date."""
    rows: list[VolumeRow] = []
    for vol in data.get("volumes") or []:
        if not isinstance(vol, dict):
            continue
        block = vol.get(locale) or {}
        if not isinstance(block, dict):
            block = {}
        rows.append(
            VolumeRow(
                number=vol.get("number"),
                title=str(vol.get("title") or ""),
                isbn=str(block.get("isbn") or ""),
                release_date=str(block.get("release_date") or ""),
            )
        )
    return rows


class ChapterTitles(NamedTuple):
    """Chapter titles resolved like ``editor inject`` (``source`` describes where)."""

    titles: dict[int, str]
    source: str
    error: str | None = None


def chapter_titles(
    data: dict[str, Any], metadata_path: Path | None, chapters_path: Path | None
) -> ChapterTitles:
    """Resolve chapter titles with ``_resolve_chapter_titles`` (never raises)."""
    yaml_dir = metadata_path.parent if metadata_path is not None else Path.cwd()
    if chapters_path is not None:
        source = f"--chapters {chapters_path}"
    elif data.get("chapters_file"):
        source = f"chapters_file: {data['chapters_file']}"
    elif data.get("chapters"):
        source = "inline chapters"
    else:
        return ChapterTitles({}, "none")
    try:
        titles = _resolve_chapter_titles(chapters_path, data, yaml_dir) or {}
    except FileNotFoundError as e:
        return ChapterTitles({}, source, f"chapters YAML not found: {e}")
    except Exception as e:  # malformed chapters YAML (bad number, YAML error …)
        return ChapterTitles({}, source, f"invalid chapters YAML: {e}")
    return ChapterTitles(dict(sorted(titles.items())), source)


# ---------------------------------------------------------------------------
# Library scan / run status
# ---------------------------------------------------------------------------


def scan_rows(result: ScanResult) -> list[dict[str, Any]]:
    """Rows for the detected-chapters table."""
    duplicated = {f for files in result.duplicates.values() for f in files}
    return [
        {
            "number": c.number,
            "extra": c.extra or "",
            "file": c.file.name,
            "duplicate": c.file in duplicated and c.extra is None,
        }
        for c in result.chapters
    ]


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    OK = "ok"
    FAILED = "failed"
    CANCELLED = "cancelled"


STATUS_COLORS: dict[StepStatus, str] = {
    StepStatus.PENDING: "grey",
    StepStatus.RUNNING: "primary",
    StepStatus.OK: "positive",
    StepStatus.FAILED: "negative",
    StepStatus.CANCELLED: "warning",
}


def step_status(result: StepResult) -> StepStatus:
    """Final status of a finished step."""
    if result.cancelled:
        return StepStatus.CANCELLED
    return StepStatus.OK if result.exit_code == 0 else StepStatus.FAILED


def display_path(path: Path | None) -> str:
    """Path as shown in forms (``""`` for ``None``)."""
    return "" if path is None else os.fspath(path)
