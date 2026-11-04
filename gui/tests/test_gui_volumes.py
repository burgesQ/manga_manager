"""Unit tests of ``manga_gui.volumes`` (volume previews helpers)."""

from __future__ import annotations

import doctest
from pathlib import Path

from manga_gui import volumes
from manga_gui.models import PackerOptions, Project
from manga_gui.volumes import (
    EpubInfo,
    expected_volume_names,
    previews_summary,
    read_epub_info,
    volume_previews,
)


def test_doctests() -> None:
    assert doctest.testmod(volumes).failed == 0


def test_read_epub_info(tmp_path: Path, make_epub) -> None:
    raw = read_epub_info(make_epub(tmp_path / "raw.epub", title="Raw"))
    assert raw.title == "Raw" and not raw.injected and raw.error is None
    full = read_epub_info(
        make_epub(
            tmp_path / "full.kepub.epub",
            inject={
                "title": "Vol 1",
                "author": "Kentaro Miura",
                "series": "Berserk",
                "series_index": 1.0,
                "isbn": "978-1-59307-020-5",
                "language": "fr",
                "tags": ["Comic", "Dark fantasy"],
            },
        )
    )
    assert full.injected
    assert (full.title, full.series, full.series_index) == ("Vol 1", "Berserk", 1.0)
    assert (full.kind, full.isbn, full.language) == ("comic", "9781593070205", "fr")
    assert full.tags == ("Comic", "Dark fantasy")
    labels = dict(full.fields())
    assert labels["Index"] == "1" and labels["Kind"] == "comic"
    assert labels["Author"] == "Kentaro Miura"


def test_read_epub_info_errors_and_cache(tmp_path: Path, make_epub) -> None:
    assert read_epub_info(tmp_path / "missing.epub").error
    bad = tmp_path / "bad.epub"
    bad.write_bytes(b"not a zip")
    assert read_epub_info(bad).error
    path = make_epub(tmp_path / "a.epub", title="A")
    first = read_epub_info(path)
    assert read_epub_info(path) is first  # cached
    assert EpubInfo().fields() == []


def test_volume_previews(tmp_path: Path, make_volume_dir, make_epub) -> None:
    dest = tmp_path / "out"
    make_volume_dir(dest, "Saga v02", chapters=3, cover=False)
    make_volume_dir(dest, "Saga v01", chapters=2)
    make_epub(dest / "Saga v01.kepub.epub", inject={"series": "Saga"})
    make_epub(dest / "Saga v10.kepub.epub")  # folder gone
    make_volume_dir(dest, "extras", chapters=0, cover=False)
    previews = volume_previews(dest, expected=["Saga v01", "Saga v03"])
    assert [(p.name, p.volume) for p in previews] == [
        ("Saga v01", 1),
        ("Saga v02", 2),
        ("Saga v03", 3),
        ("Saga v10", 10),
        ("extras", None),
    ]
    v1, v2, v3, v10, extras = previews
    assert v1.chapters == 2 and v1.cover == dest / "Saga v01" / "cover.webp"
    assert v1.epub_info is not None and v1.epub_info.series == "Saga"
    assert v2.chapters == 3 and v2.cover is None and v2.epub is None
    assert v3.planned and v3.folder is None
    assert v10.folder is None and v10.epub is not None and not v10.planned
    assert extras.chapters == 0
    assert previews_summary(previews) == (
        "3 volume folder(s), 2 EPUB(s), 1 with injected metadata, 1 not packed yet"
    )
    assert volume_previews(tmp_path / "nope") == []
    assert volume_previews(dest, read_metadata=False)[0].epub_info is None


def test_expected_volume_names(tmp_path: Path) -> None:
    project = Project(
        name="Saga",
        source=tmp_path,
        packer=PackerOptions(serie="Saga", batch="v01:1-v02:2"),
    )
    assert expected_volume_names(project) == ["Saga v01", "Saga v02"]
    project.packer.serie = None
    assert expected_volume_names(project) == []
    project.packer.serie = "Saga"
    project.packer.batch = "garbage"
    assert expected_volume_names(project) == []
