"""Shared test fixtures for editor tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytest.importorskip("ebooklib")
from ebooklib import epub


@pytest.fixture
def make_epub():
    def _make_epub(
        path: Path,
        *,
        title: str = "Title",
        author: str | None = "Author",
        publisher: str | None = None,
        toc_titles: list[str] | None = None,
    ) -> Path:
        book = epub.EpubBook()
        book.set_identifier("id123")
        book.set_title(title)
        if author:
            book.add_author(author)
        if publisher:
            book.add_metadata("DC", "publisher", publisher)

        if toc_titles is None:
            c1 = epub.EpubHtml(
                title="Intro", file_name="intro.xhtml", content="<h1>Hi</h1>"
            )
            book.add_item(c1)
            book.toc = (epub.Link("intro.xhtml", "Intro", "intro"),)
            book.spine = ["nav", c1]
        else:
            # Build one TOC entry per title, mimicking a KCC-produced volume
            # whose navLabels are the original `Chapter NNN` folder names.
            items = []
            toc = []
            for idx, label in enumerate(toc_titles):
                href = f"c{idx}.xhtml"
                item = epub.EpubHtml(
                    title=label, file_name=href, content=f"<h1>{label}</h1>"
                )
                book.add_item(item)
                items.append(item)
                toc.append(epub.Link(href, label, f"ch{idx}"))
            book.toc = tuple(toc)
            book.spine = ["nav", *items]

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        epub.write_epub(str(path), book)
        return path

    return _make_epub


@pytest.fixture
def make_yaml():
    def _make_yaml(path: Path, data: dict) -> Path:
        path.write_text(yaml.dump(data))
        return path

    return _make_yaml
