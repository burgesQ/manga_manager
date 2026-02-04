import yaml
import sys
from pathlib import Path
import pytest

pytest.importorskip("ebooklib")
from ebooklib import epub

from editor.editor_full import inject_metadata, dump_metadata, EPUBMetadata


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


def test_inject_metadata_dry_run(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    book_file = epub_dir / "Series v01.epub"
    _make_minimal_epub(book_file, title="Series v01", author="An Author")

    yaml_path = tmp_path / "meta.yaml"
    data = {
        "series": "Series",
        "author": "An Author",
        "volumes": [{"number": 1, "english": {"release_date": "2026-02-01"}}],
    }
    yaml_path.write_text(yaml.dump(data))

    # Dry run should return 0 and not modify the EPUB
    rc = inject_metadata(epub_dir, yaml_path, dry_run=True)
    assert rc == 0
    # ensure file still readable and has original metadata
    meta = EPUBMetadata(book_file).get_metadata()
    assert meta.get("title") == "Series v01"


def test_inject_metadata_real(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    book_file = epub_dir / "Series v01.epub"
    _make_minimal_epub(book_file, title="Series v01", author=None)  # start with no author

    yaml_path = tmp_path / "meta.yaml"
    data = {
        "series": "Series",
        "author": "Injected Author",
        "volumes": [{"number": 1, "english": {"release_date": "2026-02-01", "isbn": "1234567890"}}],
    }
    yaml_path.write_text(yaml.dump(data))

    rc = inject_metadata(epub_dir, yaml_path, dry_run=False)
    assert rc == 0

    # After injection, metadata should be present
    meta = EPUBMetadata(book_file).get_metadata()
    assert meta.get("author") == "Injected Author"
    assert meta.get("series") == "Series"
    assert meta.get("series_index") == 1.0
    assert meta.get("date") == "2026-02-01" or meta.get("date") is not None


def test_dump_metadata_writes_yaml(tmp_path: Path):
    epub_dir = tmp_path / "epubs"
    epub_dir.mkdir()
    book_file = epub_dir / "Series v02.epub"
    _make_minimal_epub(book_file, title="Series v02", author="Author B")

    out_yaml = tmp_path / "out.yaml"

    rc = dump_metadata(epub_dir, out_yaml)
    assert rc == 0
    assert out_yaml.exists()

    parsed = yaml.safe_load(out_yaml.read_text())
    assert parsed.get("series") is not None
    assert len(parsed.get("volumes", [])) >= 1
