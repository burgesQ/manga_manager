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
    ) -> Path:
        book = epub.EpubBook()
        book.set_identifier("id123")
        book.set_title(title)
        if author:
            book.add_author(author)
        if publisher:
            book.add_metadata("DC", "publisher", publisher)
        c1 = epub.EpubHtml(
            title="Intro", file_name="intro.xhtml", content="<h1>Hi</h1>"
        )
        book.add_item(c1)
        book.toc = (epub.Link("intro.xhtml", "Intro", "intro"),)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav", c1]
        epub.write_epub(str(path), book)
        return path

    return _make_epub


@pytest.fixture
def make_yaml():
    def _make_yaml(path: Path, data: dict) -> Path:
        path.write_text(yaml.dump(data))
        return path

    return _make_yaml
