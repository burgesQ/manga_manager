"""Tests for chapter-title TOC injection (editor --chapters feature)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("ebooklib")

from editor.cli import main
from editor.editor_full import load_chapters_yaml
from editor.epub_metadata import EPUBMetadata


def _toc_titles(path: Path) -> list[str]:
    """Return the TOC labels of an EPUB, in order."""
    meta = EPUBMetadata(path)
    return [getattr(x, "title", None) for x in meta.book.toc]


# --- EPUBMetadata.set_chapter_titles ---------------------------------------


def test_set_chapter_titles_relabels_matching_entries(make_epub, tmp_path):
    epub_path = make_epub(
        tmp_path / "vol.epub",
        toc_titles=["Chapter 000", "Chapter 001", "Chapter 002"],
    )
    meta = EPUBMetadata(epub_path)
    changed = meta.set_chapter_titles({1: "Special Grade Incident", 2: "Deterrence"})
    meta.save()

    assert changed == 2
    assert _toc_titles(epub_path) == [
        "Chapter 000",  # cover — number 0 not in map, untouched
        "Chapter 001 - Special Grade Incident",
        "Chapter 002 - Deterrence",
    ]


def test_set_chapter_titles_leaves_unmapped_untouched(make_epub, tmp_path):
    epub_path = make_epub(
        tmp_path / "vol.epub",
        toc_titles=["Chapter 001", "Chapter 002", "Chapter 003"],
    )
    meta = EPUBMetadata(epub_path)
    changed = meta.set_chapter_titles({2: "Deterrence"})
    meta.save()

    assert changed == 1
    assert _toc_titles(epub_path) == [
        "Chapter 001",
        "Chapter 002 - Deterrence",
        "Chapter 003",
    ]


def test_set_chapter_titles_roundtrips_after_reopen(make_epub, tmp_path):
    epub_path = make_epub(tmp_path / "vol.epub", toc_titles=["Chapter 001"])
    meta = EPUBMetadata(epub_path)
    meta.set_chapter_titles({1: "Special Grade Incident"})
    meta.save()

    # fresh read confirms the label survived the NCX/nav rewrite
    assert _toc_titles(epub_path) == ["Chapter 001 - Special Grade Incident"]


def test_set_chapter_titles_custom_format(make_epub, tmp_path):
    epub_path = make_epub(tmp_path / "vol.epub", toc_titles=["Chapter 005"])
    meta = EPUBMetadata(epub_path)
    meta.set_chapter_titles({5: "Senility"}, fmt="{n:03d}. {title}")
    meta.save()

    assert _toc_titles(epub_path) == ["005. Senility"]


# --- load_chapters_yaml ----------------------------------------------------


def test_load_chapters_yaml(make_yaml, tmp_path):
    path = make_yaml(
        tmp_path / "chapters.yaml",
        {
            "series": "JJKM",
            "chapters": [
                {"number": 1, "title": "Special Grade Incident", "volume": 1},
                {"number": 2, "title": "Deterrence", "volume": 1},
            ],
        },
    )
    assert load_chapters_yaml(path) == {
        1: "Special Grade Incident",
        2: "Deterrence",
    }


# --- CLI: editor inject --chapters -----------------------------------------


def test_inject_with_chapters_relabels_toc(make_epub, make_yaml, tmp_path):
    vol_dir = tmp_path / "vols"
    vol_dir.mkdir()
    # author=None -> has_metadata() is False, so metadata is injected too
    make_epub(
        vol_dir / "JJKM v01.epub",
        author=None,
        toc_titles=["Chapter 000", "Chapter 001", "Chapter 002"],
    )
    meta_yaml = make_yaml(
        tmp_path / "meta.yaml",
        {"series": "JJKM", "author": "Gege Akutami", "volumes": [{"number": 1}]},
    )
    chapters_yaml = make_yaml(
        tmp_path / "chapters.yaml",
        {
            "chapters": [
                {"number": 1, "title": "Special Grade Incident"},
                {"number": 2, "title": "Deterrence"},
            ]
        },
    )

    rc = main(
        [
            "inject",
            str(vol_dir),
            str(meta_yaml),
            "--chapters",
            str(chapters_yaml),
        ]
    )
    assert rc == 0
    titles = _toc_titles(vol_dir / "JJKM v01.epub")
    assert titles == [
        "Chapter 000",
        "Chapter 001 - Special Grade Incident",
        "Chapter 002 - Deterrence",
    ]
    # metadata was injected in the same pass
    assert EPUBMetadata(vol_dir / "JJKM v01.epub").get_metadata()["series"] == "JJKM"


def test_inject_chapters_dry_run_touches_nothing(make_epub, make_yaml, tmp_path):
    vol_dir = tmp_path / "vols"
    vol_dir.mkdir()
    epub_path = make_epub(vol_dir / "JJKM v01.epub", toc_titles=["Chapter 001"])
    before = epub_path.read_bytes()
    meta_yaml = make_yaml(
        tmp_path / "meta.yaml",
        {"series": "JJKM", "author": "Gege Akutami", "volumes": [{"number": 1}]},
    )
    chapters_yaml = make_yaml(
        tmp_path / "chapters.yaml",
        {"chapters": [{"number": 1, "title": "Special Grade Incident"}]},
    )

    rc = main(
        [
            "inject",
            str(vol_dir),
            str(meta_yaml),
            "--chapters",
            str(chapters_yaml),
            "--dry-run",
        ]
    )
    assert rc == 0
    assert epub_path.read_bytes() == before


def test_inject_chapters_file_key_in_metadata(make_epub, make_yaml, tmp_path):
    vol_dir = tmp_path / "vols"
    vol_dir.mkdir()
    make_epub(vol_dir / "JJKM v01.epub", toc_titles=["Chapter 001"])
    # chapters_file path is resolved relative to the metadata file's directory
    make_yaml(
        tmp_path / "chapters_jjkm.yaml",
        {"chapters": [{"number": 1, "title": "Special Grade Incident"}]},
    )
    meta_yaml = make_yaml(
        tmp_path / "meta.yaml",
        {
            "series": "JJKM",
            "author": "Gege Akutami",
            "chapters_file": "./chapters_jjkm.yaml",
            "volumes": [{"number": 1}],
        },
    )

    rc = main(["inject", str(vol_dir), str(meta_yaml)])
    assert rc == 0
    assert _toc_titles(vol_dir / "JJKM v01.epub") == [
        "Chapter 001 - Special Grade Incident"
    ]


def test_inject_inline_chapters_in_metadata(make_epub, make_yaml, tmp_path):
    vol_dir = tmp_path / "vols"
    vol_dir.mkdir()
    make_epub(vol_dir / "JJKM v01.epub", toc_titles=["Chapter 001"])
    meta_yaml = make_yaml(
        tmp_path / "meta.yaml",
        {
            "series": "JJKM",
            "author": "Gege Akutami",
            "chapters": [{"number": 1, "title": "Special Grade Incident"}],
            "volumes": [{"number": 1}],
        },
    )

    rc = main(["inject", str(vol_dir), str(meta_yaml)])
    assert rc == 0
    assert _toc_titles(vol_dir / "JJKM v01.epub") == [
        "Chapter 001 - Special Grade Incident"
    ]


def test_cli_chapters_overrides_metadata_key(make_epub, make_yaml, tmp_path):
    vol_dir = tmp_path / "vols"
    vol_dir.mkdir()
    make_epub(vol_dir / "JJKM v01.epub", toc_titles=["Chapter 001"])
    # metadata points at one file; CLI --chapters must win
    make_yaml(
        tmp_path / "inline.yaml",
        {"chapters": [{"number": 1, "title": "From Metadata Key"}]},
    )
    cli_chapters = make_yaml(
        tmp_path / "cli.yaml",
        {"chapters": [{"number": 1, "title": "From CLI"}]},
    )
    meta_yaml = make_yaml(
        tmp_path / "meta.yaml",
        {
            "series": "JJKM",
            "author": "Gege Akutami",
            "chapters_file": "./inline.yaml",
            "volumes": [{"number": 1}],
        },
    )

    rc = main(["inject", str(vol_dir), str(meta_yaml), "--chapters", str(cli_chapters)])
    assert rc == 0
    assert _toc_titles(vol_dir / "JJKM v01.epub") == ["Chapter 001 - From CLI"]


def test_inject_missing_chapters_file_key_errors(make_epub, make_yaml, tmp_path):
    vol_dir = tmp_path / "vols"
    vol_dir.mkdir()
    make_epub(vol_dir / "JJKM v01.epub", toc_titles=["Chapter 001"])
    meta_yaml = make_yaml(
        tmp_path / "meta.yaml",
        {
            "series": "JJKM",
            "author": "Gege Akutami",
            "chapters_file": "./does_not_exist.yaml",
            "volumes": [{"number": 1}],
        },
    )

    rc = main(["inject", str(vol_dir), str(meta_yaml)])
    assert rc == 1
