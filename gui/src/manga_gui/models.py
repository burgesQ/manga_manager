"""Project data model: per-series profile holding paths and per-step options.

The real config files (``packer.json``, batch CSV, metadata / chapters YAML) stay the
source of truth; a :class:`Project` only *points to* them and keeps the data the GUI
alone needs (paths, KCC overrides, editor locale, enabled steps).

Every dataclass round-trips through JSON via ``to_dict()`` / ``from_dict()``.
``Path`` values are serialised as ``str``; unknown keys are ignored on load so older
or newer profile files still open.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, fields
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar, Self

STEP_NAMES: tuple[str, ...] = ("packer", "convertor", "editor")
"""Pipeline steps, in execution order."""

LOCALES: tuple[str, ...] = ("english", "japanese", "french")
"""Locale blocks accepted by ``editor inject --locale``."""


class Kind(StrEnum):
    """Kind of series: drives the convertor preset (reading direction, colour)."""

    MANGA = "manga"
    COMIC = "comic"


def slugify(name: str) -> str:
    """Return a filesystem-safe slug for ``name``.

    >>> slugify("Jujutsu Kaisen (Colour)")
    'jujutsu-kaisen-colour'
    >>> slugify("Pokémon Adventures")
    'pokemon-adventures'
    >>> slugify("!!!")
    'project'
    """
    ascii_name = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or "project"


def _opt_path(value: Any) -> Path | None:
    if value is None or value == "":
        return None
    return Path(value)


class _Serializable:
    """Mixin: generic ``to_dict`` / ``from_dict`` for flat option dataclasses."""

    _PATH_FIELDS: ClassVar[frozenset[str]] = frozenset()

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for f in fields(self):  # type: ignore[arg-type]
            value = getattr(self, f.name)
            out[f.name] = str(value) if isinstance(value, Path) else value
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Self:
        data = data or {}
        known = {f.name for f in fields(cls)}  # type: ignore[arg-type]
        kwargs: dict[str, Any] = {}
        for key, value in data.items():
            if key not in known:
                continue
            kwargs[key] = _opt_path(value) if key in cls._PATH_FIELDS else value
        return cls(**kwargs)


@dataclass
class PackerOptions(_Serializable):
    """Options forwarded to ``packer``. ``None`` / defaults are not emitted."""

    _PATH_FIELDS: ClassVar[frozenset[str]] = frozenset({"config", "batch_file"})

    config: Path | None = None
    serie: str | None = None
    pattern: str = "default"
    chapter_regex: str | None = None
    extra_regex: str | None = None
    nb_worker: int = 1
    batch: str | None = None
    batch_file: Path | None = None
    volume: int | None = None
    chapter_range: str | None = None
    force: bool = False


@dataclass
class KCCOptions(_Serializable):
    """Explicit KCC overrides for ``convertor``.

    ``None`` means "not set": the convertor preset (``--preset manga|comic``) or the
    CLI default decides.
    """

    profile: str | None = None
    manga_style: bool | None = None
    hq: bool | None = None
    forcecolor: bool | None = None
    upscale: bool | None = None
    blackborders: bool | None = None
    rotation: int | None = None
    cropping: int | None = None
    force_regen: bool = False


@dataclass
class EditorOptions(_Serializable):
    """Options forwarded to ``editor inject``."""

    _PATH_FIELDS: ClassVar[frozenset[str]] = frozenset({"metadata", "chapters"})

    metadata: Path | None = None
    chapters: Path | None = None
    locale: str = "english"
    force: bool = False


def _default_steps() -> dict[str, bool]:
    return {name: True for name in STEP_NAMES}


@dataclass(kw_only=True)
class Project:
    """A per-series profile (keyword-only constructor).

    ``slug`` defaults to ``slugify(name)`` when left empty. ``dest`` defaults to
    ``source`` (see :attr:`effective_dest`), like ``packer --dest``.
    """

    name: str
    slug: str = ""
    kind: Kind = Kind.MANGA
    source: Path
    dest: Path | None = None
    packer: PackerOptions = field(default_factory=PackerOptions)
    convertor: KCCOptions = field(default_factory=KCCOptions)
    editor: EditorOptions = field(default_factory=EditorOptions)
    steps: dict[str, bool] = field(default_factory=_default_steps)

    def __post_init__(self) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        self.kind = Kind(self.kind)
        self.source = Path(self.source)
        self.dest = _opt_path(self.dest)
        self.steps = {**_default_steps(), **self.steps}

    @property
    def effective_dest(self) -> Path:
        """Destination root: ``dest`` if set, otherwise ``source``."""
        return self.dest if self.dest is not None else self.source

    def step_enabled(self, step: str) -> bool:
        """Return True when ``step`` is enabled (unknown steps are disabled)."""
        return bool(self.steps.get(step, False))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "slug": self.slug,
            "kind": self.kind.value,
            "source": str(self.source),
            "dest": str(self.dest) if self.dest is not None else None,
            "packer": self.packer.to_dict(),
            "convertor": self.convertor.to_dict(),
            "editor": self.editor.to_dict(),
            "steps": dict(self.steps),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        steps = data.get("steps") or {}
        return cls(
            name=str(data["name"]),
            slug=str(data.get("slug") or ""),
            kind=Kind(data.get("kind", Kind.MANGA.value)),
            source=Path(data["source"]),
            dest=_opt_path(data.get("dest")),
            packer=PackerOptions.from_dict(data.get("packer")),
            convertor=KCCOptions.from_dict(data.get("convertor")),
            editor=EditorOptions.from_dict(data.get("editor")),
            steps={str(k): bool(v) for k, v in steps.items()},
        )


@dataclass
class Settings(_Serializable):
    """App-wide settings (``<config>/settings.json``), not tied to a project.

    - ``library_root``: folder holding the series folders (``<root>/<LANG>/<dir>``);
    - ``metadata_dir``: folder of per-series files (``packer_<key>.json``,
      ``<key>.yaml``, ``chapters_<key>.yaml``, ``vols_<key>.csv``).
    """

    _PATH_FIELDS: ClassVar[frozenset[str]] = frozenset({"library_root", "metadata_dir"})

    library_root: Path | None = None
    metadata_dir: Path | None = None

    def merged(self, overrides: Settings) -> Settings:
        """Copy of ``self`` where every non-``None`` value of ``overrides`` wins.

        >>> base = Settings(library_root=Path("/a"), metadata_dir=Path("/m"))
        >>> base.merged(Settings(library_root=Path("/b")))
        Settings(library_root=PosixPath('/b'), metadata_dir=PosixPath('/m'))
        """
        return Settings(
            library_root=overrides.library_root or self.library_root,
            metadata_dir=overrides.metadata_dir or self.metadata_dir,
        )
