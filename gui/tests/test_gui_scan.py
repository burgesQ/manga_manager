from __future__ import annotations

from pathlib import Path

from manga_gui.models import PackerOptions, Project
from manga_gui.scan import list_epubs, list_volume_dirs, scan_library


def test_scan_default_pattern(tmp_path: Path, make_library) -> None:
    src = make_library(
        tmp_path / "lib",
        [
            "Berserk Chapter 2.cbz",
            "Berserk Chapter 1.cbz",
            "Berserk Chapter 1.5.cbz",
            "readme.cbz",
        ],
    )
    (src / "notes.txt").write_text("not a cbz")
    p = Project(
        name="B",
        source=src,
        packer=PackerOptions(serie="B", volume=1, chapter_range="1..3"),
    )
    res = scan_library(p)
    assert [(c.label, c.file.name) for c in res.chapters] == [
        ("1", "Berserk Chapter 1.cbz"),
        ("1.5", "Berserk Chapter 1.5.cbz"),
        ("2", "Berserk Chapter 2.cbz"),
    ]
    assert [f.name for f in res.unmatched] == ["readme.cbz"]
    assert res.duplicates == {}
    assert res.missing == [3]
    assert res.errors == []


def test_scan_named_pattern_from_packer_json(
    tmp_path: Path, make_library, write_json
) -> None:
    src = make_library(tmp_path / "lib", ["Serie #001.cbz", "Serie #002.5.cbz"])
    write_json(src / "packer.json", {"pattern": "weebcentral"})
    res = scan_library(Project(name="S", source=src))
    assert [(c.number, c.extra) for c in res.chapters] == [(1, None), (2, "5")]
    assert res.unmatched == []
    assert res.missing == []


def test_scan_custom_regex_and_duplicates(tmp_path: Path, make_library) -> None:
    src = make_library(
        tmp_path / "lib", ["Saga 001 (2012).cbz", "Saga 001 (HD).cbz", "Saga 002.cbz"]
    )
    p = Project(
        name="Saga",
        source=src,
        packer=PackerOptions(chapter_regex=r"Saga 0*(\d+)", batch="v01:1..2"),
    )
    res = scan_library(p)
    assert sorted(f.name for f in res.duplicates[1]) == [
        "Saga 001 (2012).cbz",
        "Saga 001 (HD).cbz",
    ]
    assert [c.number for c in res.chapters] == [1, 1, 2]
    assert res.missing == []


def test_scan_reports_errors(tmp_path: Path, make_library) -> None:
    src = make_library(tmp_path / "lib", ["Chapter 1.cbz"])
    (src / "packer.json").write_text("{bad")
    p = Project(name="x", source=src, packer=PackerOptions(chapter_regex="("))
    res = scan_library(p)
    assert len(res.errors) == 2
    assert "Invalid packer.json" in res.errors[0]
    assert "invalid regex" in res.errors[1]
    # Falls back to the legacy patterns.
    assert [c.number for c in res.chapters] == [1]


def test_scan_missing_source(tmp_path: Path) -> None:
    res = scan_library(Project(name="x", source=tmp_path / "nope"))
    assert res.chapters == [] and res.errors and "cannot list" in res.errors[0]


def test_list_volume_dirs_and_epubs(tmp_path: Path) -> None:
    assert list_volume_dirs(tmp_path / "missing") == []
    assert list_epubs(tmp_path / "missing") == []
    v1 = tmp_path / "Berserk v01"
    (v1 / "Chapter 001").mkdir(parents=True)
    (v1 / "Chapter 002").mkdir()
    (v1 / "cover.webp").write_bytes(b"x")
    (tmp_path / "Berserk v02").mkdir()
    (tmp_path / "misc").mkdir()
    (tmp_path / "Berserk v01.kepub.epub").write_bytes(b"x")
    (tmp_path / "other.epub").write_bytes(b"x")
    (tmp_path / "Chapter 1.cbz").write_bytes(b"x")

    vols = list_volume_dirs(tmp_path)
    assert [(v.name, v.volume, v.chapters) for v in vols] == [
        ("Berserk v01", 1, 2),
        ("Berserk v02", 2, 0),
        ("misc", None, 0),
    ]
    assert vols[0].cover == v1 / "cover.webp"
    assert vols[0].epub == tmp_path / "Berserk v01.kepub.epub"
    assert vols[1].cover is None and vols[1].epub is None
    assert [p.name for p in list_epubs(tmp_path)] == [
        "Berserk v01.kepub.epub",
        "other.epub",
    ]
