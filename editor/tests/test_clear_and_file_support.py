import pytest
from pathlib import Path

pytest.importorskip("ebooklib")
from ebooklib import epub

from editor.editor_full import clear_metadata, EPUBMetadata, inject_metadata, dump_metadata


def _make_minimal_epub(path: Path, title: str = "Title", author: str | None = "Author"):
    """Helper to create a minimal EPUB with optional author."""
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


def test_clear_metadata_from_single_file(tmp_path: Path):
    """Test clearing metadata from a single EPUB file."""
    book_file = tmp_path / "Series v01.epub"
    _make_minimal_epub(book_file, title="Series v01", author="An Author")
    
    # Verify it has metadata before clearing
    meta = EPUBMetadata(book_file).get_metadata()
    assert meta.get("title") == "Series v01"
    assert meta.get("author") == "An Author"
    
    # Clear metadata
    rc = clear_metadata(book_file, dry_run=False)
    assert rc == 0
    
    # Verify metadata author field is cleared (empty list removes authors)
    meta_after = EPUBMetadata(book_file).get_metadata()
    # After clearing with empty author list, author should be gone or empty
    assert meta_after.get("author") is None or meta_after.get("author") == []


def test_clear_metadata_from_directory(tmp_path: Path):
    """Test clearing metadata from a directory of EPUBs."""
    dir_path = tmp_path / "epubs"
    dir_path.mkdir()
    
    # Create multiple EPUB files
    for i in range(1, 3):
        _make_minimal_epub(dir_path / f"Series v{i:02d}.epub", 
                          title=f"Series v{i:02d}", 
                          author="An Author")
    
    # Clear metadata
    rc = clear_metadata(dir_path, dry_run=False)
    assert rc == 0
    
    # Verify all files are cleared
    for i in range(1, 3):
        meta = EPUBMetadata(dir_path / f"Series v{i:02d}.epub").get_metadata()
        assert meta.get("author") is None or meta.get("author") == []


def test_clear_metadata_dry_run(tmp_path: Path):
    """Test dry run doesn't actually modify files."""
    book_file = tmp_path / "Series v01.epub"
    _make_minimal_epub(book_file, title="Series v01", author="An Author")
    
    # Run dry run
    rc = clear_metadata(book_file, dry_run=True)
    assert rc == 0
    
    # Verify file is unchanged
    meta = EPUBMetadata(book_file).get_metadata()
    assert meta.get("author") == "An Author"


def test_dump_metadata_from_single_file(tmp_path: Path):
    """Test dumping metadata from a single EPUB file."""
    book_file = tmp_path / "Series v01.epub"
    _make_minimal_epub(book_file, title="Series v01", author="An Author")
    
    out_yaml = tmp_path / "out.yaml"
    rc = dump_metadata(book_file, out_yaml)
    assert rc == 0
    assert out_yaml.exists()


def test_inject_metadata_into_single_file(tmp_path: Path):
    """Test injecting metadata into a single file."""
    import yaml
    
    book_file = tmp_path / "Series v01.epub"
    _make_minimal_epub(book_file, title="Series v01", author=None)
    
    yaml_path = tmp_path / "meta.yaml"
    data = {
        "series": "Series",
        "author": "Injected Author",
        "volumes": [{"number": 1, "english": {"release_date": "2026-02-01"}}],
    }
    yaml_path.write_text(yaml.dump(data))
    
    rc = inject_metadata(book_file, yaml_path, dry_run=False)
    assert rc == 0
    
    # Verify metadata was injected
    meta = EPUBMetadata(book_file).get_metadata()
    assert meta.get("author") == "Injected Author"
    assert meta.get("series") == "Series"
