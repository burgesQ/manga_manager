"""Tests for uncovered paths in editor_full.py."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytest.importorskip("ebooklib")
from ebooklib import epub

from editor.editor_full import (
    EPUBMetadata,
    clear_metadata,
    dump_metadata,
    inject_metadata,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_epub(
    path: Path,
    *,
    title: str = "Title",
    author: str | None = "Author",
    publisher: str | None = None,
) -> Path:
    book = epub.EpubBook()
    book.set_identifier("id123")
    book.set_title(title)
    if author:
        book.add_author(author)
    if publisher:
        book.add_metadata("DC", "publisher", publisher)
    c1 = epub.EpubHtml(title="Intro", file_name="intro.xhtml", content="<h1>Hi</h1>")
    book.add_item(c1)
    book.toc = (epub.Link("intro.xhtml", "Intro", "intro"),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1]
    epub.write_epub(str(path), book)
    return path


def _make_yaml(path: Path, data: dict) -> Path:
    path.write_text(yaml.dump(data))
    return path


# ---------------------------------------------------------------------------
# EPUBMetadata._load() — bad file (lines 46-47)
# ---------------------------------------------------------------------------


def test_epub_metadata_load_bad_file(tmp_path: Path):
    bad = tmp_path / "bad.epub"
    bad.write_bytes(b"not a zip file at all")
    with pytest.raises(ValueError, match="Failed to load EPUB"):
        EPUBMetadata(bad)


# ---------------------------------------------------------------------------
# get_metadata() — publisher branch (line 95)
# ---------------------------------------------------------------------------


def test_get_metadata_with_publisher(tmp_path: Path):
    epub_path = tmp_path / "Series v01.epub"
    _make_epub(epub_path, publisher="Dark Horse Comics")
    meta = EPUBMetadata(epub_path).get_metadata()
    assert meta.get("publisher") == "Dark Horse Comics"


# ---------------------------------------------------------------------------
# get_metadata() — invalid series_index silently ignored (lines 145-146)
# ---------------------------------------------------------------------------


def test_get_metadata_invalid_series_index(tmp_path: Path):
    epub_path = tmp_path / "Series v01.epub"
    _make_epub(epub_path)
    em = EPUBMetadata(epub_path)
    opf_ns = "http://www.idpf.org/2007/opf"
    meta_list = em.book.metadata.setdefault(opf_ns, {}).setdefault("meta", [])
    meta_list.append(("MySeries", {"name": "calibre:series"}))
    meta_list.append(("not-a-float", {"name": "calibre:series_index"}))
    result = em.get_metadata()
    assert result.get("series") == "MySeries"
    assert "series_index" not in result


# ---------------------------------------------------------------------------
# set_metadata() — dc_ns missing branch (line 178) + publisher (line 190)
# ---------------------------------------------------------------------------


def test_set_metadata_no_dc_namespace(tmp_path: Path):
    """When dc namespace is absent from metadata, it is initialised."""
    epub_path = tmp_path / "Series v01.epub"
    _make_epub(epub_path)
    em = EPUBMetadata(epub_path)
    dc_ns = "http://purl.org/dc/elements/1.1/"
    em.book.metadata.pop(dc_ns, None)
    em.set_metadata(author="New Author")
    assert dc_ns in em.book.metadata


def test_set_metadata_with_publisher(tmp_path: Path):
    epub_path = tmp_path / "Series v01.epub"
    _make_epub(epub_path)
    em = EPUBMetadata(epub_path)
    em.set_metadata(title="My Title", publisher="My Publisher")
    em.save()
    meta = EPUBMetadata(epub_path).get_metadata()
    assert meta.get("publisher") == "My Publisher"


# ---------------------------------------------------------------------------
# inject_metadata — un-parseable filename skipped (lines 352-353)
# ---------------------------------------------------------------------------


def test_inject_unparseable_filename(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    _make_epub(epub_dir / "no_number_here.epub")
    yaml_path = _make_yaml(
        tmp_path / "meta.yaml",
        {"series": "S", "author": "A", "volumes": [{"number": 1}]},
    )
    rc = inject_metadata(epub_dir, yaml_path)
    assert rc == 0


# ---------------------------------------------------------------------------
# inject_metadata — dry_run branch (line 392)
# ---------------------------------------------------------------------------


def test_inject_dry_run_logs_no_save(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    epub_path = epub_dir / "Series v01.epub"
    # EPUB without author → has_metadata() returns False → dry_run branch is reached
    _make_epub(epub_path, author=None)
    mtime_before = epub_path.stat().st_mtime
    yaml_path = _make_yaml(
        tmp_path / "meta.yaml",
        {"series": "Series", "author": "Author", "volumes": [{"number": 1}]},
    )
    rc = inject_metadata(epub_dir, yaml_path, dry_run=True)
    assert rc == 0
    assert epub_path.stat().st_mtime == mtime_before


# ---------------------------------------------------------------------------
# inject_metadata — exception handler (lines 419-421)
# ---------------------------------------------------------------------------


def test_inject_corrupted_epub_error_counted(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    (epub_dir / "Series v01.epub").write_bytes(b"not a zip")
    yaml_path = _make_yaml(
        tmp_path / "meta.yaml",
        {"series": "S", "author": "A", "volumes": [{"number": 1}]},
    )
    rc = inject_metadata(epub_dir, yaml_path)
    assert rc == 1


# ---------------------------------------------------------------------------
# dump_metadata — no EPUB files (lines 449-450)
# ---------------------------------------------------------------------------


def test_dump_no_epub_files(tmp_path: Path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    rc = dump_metadata(empty_dir, None)
    assert rc == 1


# ---------------------------------------------------------------------------
# dump_metadata — publisher + date/isbn (lines 474, 493-494, 503)
# ---------------------------------------------------------------------------


def test_dump_captures_publisher_date_isbn(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    epub_path = epub_dir / "Series v01.epub"
    _make_epub(epub_path, publisher="Dark Horse Comics")
    em = EPUBMetadata(epub_path)
    em.set_metadata(date="2023-01-01", isbn="1234567890")
    em.save()

    out_yaml = tmp_path / "out.yaml"
    rc = dump_metadata(epub_dir, out_yaml)
    assert rc == 0
    parsed = yaml.safe_load(out_yaml.read_text())
    assert parsed.get("publisher") == "Dark Horse Comics"


# ---------------------------------------------------------------------------
# dump_metadata — exception in loop (lines 493-494)
# ---------------------------------------------------------------------------


def test_dump_corrupted_epub_continues(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    _make_epub(epub_dir / "Series v01.epub")
    (epub_dir / "Series v02.epub").write_bytes(b"not a zip")
    rc = dump_metadata(epub_dir, None)
    assert rc == 0


# ---------------------------------------------------------------------------
# clear_metadata — exception handler (lines 607-609)
# ---------------------------------------------------------------------------


def test_clear_corrupted_epub_error_counted(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    _make_epub(epub_dir / "Series v01.epub")
    (epub_dir / "Series v02.epub").write_bytes(b"not a zip")
    rc = clear_metadata(epub_dir)
    assert rc == 1
