"""Tests for the language field handling in :func:`inject_metadata`.

The EPUB language was previously hardcoded to ``en-US``. These tests
verify that the language is now resolved from the metadata YAML, with a
``en-US`` fallback when no language is provided.
"""

from pathlib import Path

import pytest
import yaml

pytest.importorskip("ebooklib")
from ebooklib import epub

from editor.editor_full import EPUBMetadata, inject_metadata


def _make_minimal_epub(path: Path, title: str = "Title", author: str | None = "Author"):
    book = epub.EpubBook()
    book.set_identifier("id123")
    book.set_title(title)
    if author:
        book.add_author(author)
    c1 = epub.EpubHtml(title="Intro", file_name="intro.xhtml", content="<h1>Hi</h1>")
    book.add_item(c1)
    book.toc = (epub.Link("intro.xhtml", "Intro", "intro"),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1]
    epub.write_epub(str(path), book)


def _inject_and_read(tmp_path: Path, yaml_data: dict) -> str | None:
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    book_file = epub_dir / "Series v01.epub"
    _make_minimal_epub(book_file, title="Series v01", author=None)

    yaml_path = tmp_path / "meta.yaml"
    yaml_path.write_text(yaml.dump(yaml_data))

    rc = inject_metadata(epub_dir, yaml_path, dry_run=False)
    assert rc == 0

    return EPUBMetadata(book_file).get_metadata().get("language")


def test_inject_language_from_yaml(tmp_path: Path):
    """A YAML with ``language: fr`` results in ``fr`` on the EPUB."""
    data = {
        "series": "Series",
        "author": "An Author",
        "language": "fr",
        "volumes": [{"number": 1, "english": {"release_date": "2026-02-01"}}],
    }
    assert _inject_and_read(tmp_path, data) == "fr"


def test_inject_language_defaults_to_en_us(tmp_path: Path):
    """A YAML without a ``language`` key defaults to ``en-US``."""
    data = {
        "series": "Series",
        "author": "An Author",
        "volumes": [{"number": 1, "english": {"release_date": "2026-02-01"}}],
    }
    assert _inject_and_read(tmp_path, data) == "en-US"


def test_inject_language_per_volume_overrides_series(tmp_path: Path):
    """A per-volume ``language`` value overrides the series-level value."""
    data = {
        "series": "Series",
        "author": "An Author",
        "language": "en-US",
        "volumes": [
            {
                "number": 1,
                "language": "ja",
                "english": {"release_date": "2026-02-01"},
            }
        ],
    }
    assert _inject_and_read(tmp_path, data) == "ja"
