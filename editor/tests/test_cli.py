"""Tests for editor/cli.py — inject/dump/clear subcommands."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytest.importorskip("ebooklib")
from ebooklib import epub

from editor.cli import main

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_epub(path: Path, title: str = "Title", author: str = "Author") -> Path:
    book = epub.EpubBook()
    book.set_identifier("id123")
    book.set_title(title)
    book.add_author(author)
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
# No subcommand → print help, return 1
# ---------------------------------------------------------------------------


def test_main_no_command():
    assert main([]) == 1


# ---------------------------------------------------------------------------
# inject subcommand
# ---------------------------------------------------------------------------


def test_main_inject_success(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    _make_epub(epub_dir / "Series v01.epub")
    yaml_path = _make_yaml(
        tmp_path / "meta.yaml",
        {
            "series": "Series",
            "author": "Author",
            "volumes": [{"number": 1, "english": {"release_date": "2026-01-01"}}],
        },
    )
    rc = main(["inject", str(epub_dir), str(yaml_path)])
    assert rc == 0


def test_main_inject_dry_run(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    _make_epub(epub_dir / "Series v01.epub")
    yaml_path = _make_yaml(
        tmp_path / "meta.yaml",
        {"series": "S", "author": "A", "volumes": [{"number": 1}]},
    )
    rc = main(["inject", str(epub_dir), str(yaml_path), "--dry-run"])
    assert rc == 0


def test_main_inject_missing_yaml(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    _make_epub(epub_dir / "Series v01.epub")
    rc = main(["inject", str(epub_dir), str(tmp_path / "nonexistent.yaml")])
    assert rc == 1


# ---------------------------------------------------------------------------
# dump subcommand
# ---------------------------------------------------------------------------


def test_main_dump_stdout(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    _make_epub(epub_dir / "Series v01.epub")
    rc = main(["dump", str(epub_dir)])
    assert rc == 0


def test_main_dump_to_file(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    _make_epub(epub_dir / "Series v01.epub")
    out = tmp_path / "out.yaml"
    rc = main(["dump", str(epub_dir), "--output", str(out)])
    assert rc == 0
    assert out.exists()


def test_main_dump_empty_dir(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    rc = main(["dump", str(empty)])
    assert rc == 1


# ---------------------------------------------------------------------------
# clear subcommand
# ---------------------------------------------------------------------------


def test_main_clear_success(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    _make_epub(epub_dir / "Series v01.epub")
    rc = main(["clear", str(epub_dir)])
    assert rc == 0


def test_main_clear_dry_run(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    _make_epub(epub_dir / "Series v01.epub")
    rc = main(["clear", str(epub_dir), "--dry-run"])
    assert rc == 0
