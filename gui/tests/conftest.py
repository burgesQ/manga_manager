"""Shared factory fixtures for manga_gui tests."""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, NamedTuple

import pytest
import yaml
from ebooklib import epub
from manga_gui.commands import StepCommand
from manga_gui.models import Project
from manga_gui.pages import register_pages
from manga_gui.store import Store
from nicegui.testing import User, user_simulation

from editor.epub_metadata import EPUBMetadata
from packer.testing import make_cbz as _packer_make_cbz


@pytest.fixture
def make_project() -> Callable[..., Project]:
    """Build a Project for ``source`` (name defaults to ``Berserk``)."""

    def _make(source: Path, *, name: str = "Berserk", **kwargs: Any) -> Project:
        return Project(name=name, source=source, **kwargs)

    return _make


@pytest.fixture
def make_library() -> Callable[..., Path]:
    """Create ``root`` and one ``.cbz`` (with ComicInfo.xml) per file name."""

    def _make(root: Path, names: list[str], *, include_comicinfo: bool = True) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        for name in names:
            _packer_make_cbz(root, name, include_comicinfo=include_comicinfo)
        return root

    return _make


@pytest.fixture
def write_json() -> Callable[[Path, Any], Path]:
    def _write(path: Path, data: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def write_yaml() -> Callable[[Path, Any], Path]:
    def _write(path: Path, data: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def py_cmd(tmp_path: Path) -> Callable[..., StepCommand]:
    """A StepCommand running ``python -c <code>`` in ``tmp_path``."""

    def _make(code: str, *, step: str = "packer") -> StepCommand:
        return StepCommand(step=step, argv=[sys.executable, "-c", code], cwd=tmp_path)

    return _make


@pytest.fixture
def make_epub() -> Callable[..., Path]:
    """Write a minimal EPUB at ``path``; ``inject`` adds editor metadata to it.

    ``inject`` holds keyword arguments for ``EPUBMetadata.set_metadata`` (title,
    series, series_index, isbn, language, tags …), applied like ``editor inject``.
    """

    def _make(
        path: Path, *, title: str = "Raw", inject: dict[str, Any] | None = None
    ) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        book = epub.EpubBook()
        book.set_identifier("id123")
        book.set_title(title)
        page = epub.EpubHtml(title="p1", file_name="p1.xhtml", content="<p>1</p>")
        book.add_item(page)
        book.toc = (epub.Link("p1.xhtml", "Chapter 001", "c1"),)
        book.spine = ["nav", page]
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        epub.write_epub(str(path), book)
        if inject is not None:
            meta = EPUBMetadata(path)
            meta.set_metadata(**inject)
            meta.save()
        return path

    return _make


@pytest.fixture
def make_volume_dir() -> Callable[..., Path]:
    """Create ``dest/<name>/`` with ``chapters`` ``Chapter NNN`` folders (+ cover)."""

    def _make(dest: Path, name: str, *, chapters: int = 2, cover: bool = True) -> Path:
        vol = dest / name
        for n in range(1, chapters + 1):
            (vol / f"Chapter {n:03d}").mkdir(parents=True)
        vol.mkdir(parents=True, exist_ok=True)
        if cover:
            (vol / "cover.webp").write_bytes(b"RIFF0000WEBP")
        return vol

    return _make


class Shelf(NamedTuple):
    """A fake library root + metadata dir (see :func:`fake_shelf`)."""

    root: Path
    meta: Path


def _vol(series: Path, serie: str, n: int = 1) -> None:
    (series / f"{serie} v{n:02d}" / "Chapter 001").mkdir(parents=True)


@pytest.fixture
def fake_shelf(tmp_path: Path, write_json, write_yaml) -> Shelf:
    """A library root ``shelf/<LANG>/<dir>`` and a metadata dir mirroring the
    real layout.

    Expected matches: fma, jjk, jjkm, zetman (covers) → EN/FmA, EN/JJK, EN/JJKM,
    EN/Zetman; mashle (yaml series; invalid packer json) → EN/Mashle; boruto
    (key) → FR/Boruto; boruto_bv (initials) → FR/BorutoBlueVortex; shangri
    (prefix) → FR/Shangri-La Frontier; EN/Berserk has no metadata; vinland has
    no folder; NickelMenu (a git repo), ``.Trash`` and loose files are ignored.
    """
    root, meta = tmp_path / "shelf", tmp_path / "metadatas"
    en, fr = root / "EN", root / "FR"

    def vols(locale: str) -> list[dict[str, Any]]:
        return [{"number": 1, "title": "One", locale: {"isbn": "123"}}]

    def packer(key: str, serie: str, folder: Path, **extra: Any) -> None:
        data = {
            "serie": serie,
            "batch_file": str(meta / f"vols_{key}.csv"),
            "covers": {"1": str(folder / "covers" / "1.webp")},
            **extra,
        }
        write_json(meta / f"packer_{key}.json", data)
        (meta / f"vols_{key}.csv").write_text("v01,1\n")
        (folder / "covers").mkdir(parents=True)

    # EN
    _vol(en / "Berserk", "Berserk", 1)
    _vol(en / "Berserk", "Berserk", 2)
    packer("fma", "Fullmetal Alchemist", en / "FmA")
    _vol(en / "FmA", "Fullmetal Alchemist")
    write_json(en / "FmA" / "packer.json", {"serie": "Fullmetal Alchemist"})
    write_yaml(
        meta / "fma.yaml", {"series": "Fullmetal Alchemist", "volumes": vols("english")}
    )
    packer("jjk", "Jujutsu Kaisen", en / "JJK")
    (en / "JJK" / "Ch.001.cbz").write_bytes(b"PK")
    write_yaml(
        meta / "jjk.yaml",
        {
            "series": "Jujutsu Kaisen",
            "chapters_file": "./chapters_jjk.yaml",
            "volumes": vols("english"),
        },
    )
    write_yaml(meta / "chapters_jjk.yaml", {"chapters": [{"number": 1, "title": "A"}]})
    packer("jjkm", "Jujutsu Kaisen Modulo", en / "JJKM")
    _vol(en / "JJKM", "Jujutsu Kaisen Modulo")
    write_yaml(
        meta / "jjkm.yaml",
        {"series": "Jujutsu Kaisen Modulo", "volumes": vols("english")},
    )
    write_yaml(meta / "chapters_jjkm.yaml", {"chapters": []})
    packer("zetman", "Zetman", en / "Zetman", kind="comic")
    write_yaml(meta / "zetman.yaml", {"series": "Zetman", "volumes": vols("japanese")})
    _vol(en / "Mashle", "Mashle")
    (en / "Mashle" / "packer.json").write_text('{"serie": "Mashle" "x": 1}')
    (meta / "packer_mashle.json").write_text('{"serie": "Mashle"\n "covers": {}}')
    write_yaml(meta / "mashle.yaml", {"series": "Mashle", "volumes": vols("english")})

    # FR
    boruto = {"series": "Boruto: Naruto Next Generations", "volumes": vols("english")}
    _vol(fr / "Boruto", "Boruto")
    write_json(fr / "Boruto" / "packer.json", {"serie": "Boruto"})
    write_yaml(meta / "boruto.yaml", boruto)
    _vol(fr / "BorutoBlueVortex", "Boruto Two Blue Vortex")
    write_json(
        fr / "BorutoBlueVortex" / "packer.json", {"serie": "Boruto: Two Blue Vortex"}
    )
    write_yaml(meta / "boruto_bv.yaml", boruto)
    _vol(fr / "Shangri-La Frontier", "Shangri-La Frontier")
    write_yaml(
        meta / "shangri.yaml",
        {"series": "Shangri-La Frontier ~Kusoge Hunter~", "volumes": vols("french")},
    )

    # group without folder
    write_yaml(meta / "vinland.yaml", {"series": "Vinland Saga", "volumes": []})

    # noise: a git repository, hidden folder, loose files
    nickel = root / "NickelMenu"
    (nickel / ".git").mkdir(parents=True)
    (nickel / "src").mkdir()
    (nickel / "src" / "trap.cbz").write_bytes(b"PK")  # never reached
    (nickel / "res" / "doc").mkdir(parents=True)
    (nickel / "test" / "syms").mkdir(parents=True)
    _vol(root / ".Trash", "Old")
    (root / "kcc.AppImage").write_bytes(b"\x7fELF")
    (root / "TODOs.org").write_text("* TODO\n")
    (meta / "notes.txt").write_text("not a metadata file\n")
    return Shelf(root, meta)


# -- NiceGUI user simulation -------------------------------------------------
#
# The ``nicegui.testing.user_plugin`` fixtures are not registered: a
# ``pytest_plugins`` in a non-root conftest is an error, and the plugin's ``user``
# fixture needs an async test runner plus a ``main_file``. Instead NiceGUI's
# documented ``user_simulation()`` context manager is driven through the anyio
# pytest plugin (already installed): mark UI tests with ``@pytest.mark.anyio``.


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def gui_store(tmp_path: Path) -> Store:
    """Store under ``tmp_path/data`` used by the pages of :func:`gui_user`."""
    return Store(tmp_path / "data")


@pytest.fixture
async def gui_user(gui_store: Store) -> AsyncIterator[User]:
    """Simulated NiceGUI user with the manga-gui pages registered on ``gui_store``.

    NiceGUI's reset drops the page modules from ``sys.modules`` on exit; they are
    put back so later imports keep resolving to the module objects (and classes)
    the tests already hold.
    """
    saved = {
        name: mod
        for name, mod in sys.modules.items()
        if name == "manga_gui" or name.startswith("manga_gui.")
    }
    try:
        async with user_simulation() as user:
            register_pages(gui_store)
            yield user
    finally:
        sys.modules.update(saved)
