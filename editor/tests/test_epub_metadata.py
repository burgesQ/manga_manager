import pytest
from pathlib import Path

pytest.importorskip("ebooklib")
from ebooklib import epub

from editor.editor_full import EPUBMetadata


def test_epubmetadata_reads_title_and_author(tmp_path: Path):
    book = epub.EpubBook()
    book.set_identifier("id123")
    book.set_title("My Title")
    book.add_author("An Author")
    # add a minimal content item and required navigation structures
    c1 = epub.EpubHtml(title="Intro", file_name="intro.xhtml", content="<h1>Hi</h1>")
    book.add_item(c1)
    book.toc = (epub.Link("intro.xhtml", "Intro", "intro"),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1]

    out = tmp_path / "book.epub"
    epub.write_epub(str(out), book)

    em = EPUBMetadata(out)
    meta = em.get_metadata()
    assert meta.get("title") == "My Title"
    assert meta.get("author") == "An Author"
    assert em.has_metadata()
