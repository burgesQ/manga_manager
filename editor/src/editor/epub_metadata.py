"""Low-level EPUB metadata I/O via ebooklib."""

from __future__ import annotations

import logging
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

try:
    from ebooklib import epub
except ImportError:
    print("Error: ebooklib not installed. Install with: pip install ebooklib")
    sys.exit(1)

logger = logging.getLogger(__name__)


def _dc_scalar(dc: dict, field: str) -> str | None:
    """Return the first scalar value for a Dublin Core field, or None.

    ebooklib stores DC entries as a list of ``(value, attrs)`` tuples or bare
    strings; this helper normalises both forms.
    """
    entries = dc.get(field)
    if not entries:
        return None
    entry = entries[0]
    return entry[0] if isinstance(entry, tuple) else entry


class EPUBMetadata:
    """Container for EPUB metadata."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.book = None
        self._load()

    def _load(self):
        """Load EPUB file."""
        try:
            self.book = epub.read_epub(str(self.filepath))
        except (OSError, KeyError, zipfile.BadZipFile, epub.EpubException) as e:
            raise ValueError(f"Failed to load EPUB {self.filepath}: {e}") from e

    def has_metadata(self) -> bool:
        """Check if EPUB already has metadata set."""
        meta = self.book.metadata.get("http://www.idpf.org/2007/opf", {})

        for item in meta.get("meta", []):
            if isinstance(item, tuple) and len(item) >= 2:
                attrs = item[1] if len(item) > 1 else {}
                if isinstance(attrs, dict):
                    if attrs.get("name") == "calibre:series":
                        return True

        dc_meta = self.book.metadata.get("http://purl.org/dc/elements/1.1/", {})
        has_title = bool(dc_meta.get("title"))
        has_creator = bool(dc_meta.get("creator"))

        return has_title and has_creator

    def get_metadata(self) -> dict[str, Any]:
        """Extract current metadata from EPUB."""
        meta = {}

        dc = self.book.metadata.get("http://purl.org/dc/elements/1.1/", {})
        logger.debug(f"meta: {dc}")

        for field in ("title", "publisher", "date", "language"):
            val = _dc_scalar(dc, field)
            if val:
                meta[field] = val

        if dc.get("creator"):
            creators = [c[0] if isinstance(c, tuple) else c for c in dc["creator"]]
            meta["author"] = creators[0] if len(creators) == 1 else creators

        for identifier in dc.get("identifier", []):
            id_value = identifier[0] if isinstance(identifier, tuple) else identifier
            attrs = (
                identifier[1]
                if isinstance(identifier, tuple) and len(identifier) > 1
                else {}
            )
            if isinstance(attrs, dict) and attrs.get("id") == "isbn":
                meta["isbn"] = id_value
                break

        opf_meta = self.book.metadata.get("http://www.idpf.org/2007/opf", {})
        logger.debug(f"opf meta: {opf_meta}")

        for item in opf_meta.get("meta", []):
            if isinstance(item, tuple) and len(item) >= 2:
                content = item[0]
                attrs = item[1] if len(item) > 1 else {}
                if isinstance(attrs, dict):
                    name = attrs.get("name", "")
                    if name == "calibre:series":
                        meta["series"] = content
                    elif name == "calibre:series_index":
                        try:
                            meta["series_index"] = float(content)
                        except (ValueError, TypeError):
                            pass

        return meta

    def set_metadata(
        self,
        title: str | None = None,
        author: str | list[str] | None = None,
        series: str | None = None,
        series_index: float | None = None,
        date: str | None = None,
        isbn: str | None = None,
        publisher: str | None = None,
        language: str = "en-US",
    ):
        """Set metadata in EPUB file.

        TODO: set calibre tags (genre & other)
        """

        if title:
            dc_ns = "http://purl.org/dc/elements/1.1/"
            if dc_ns in self.book.metadata and "title" in self.book.metadata[dc_ns]:
                self.book.metadata[dc_ns]["title"] = []
            self.book.set_title(title)

        if author is not None:
            dc_ns = "http://purl.org/dc/elements/1.1/"
            if dc_ns not in self.book.metadata:
                self.book.metadata[dc_ns] = {}
            self.book.metadata[dc_ns]["creator"] = []

            if author:
                authors = [author] if isinstance(author, str) else author
                for auth in authors:
                    self.book.add_author(auth)

        if publisher:
            self.book.add_metadata("DC", "publisher", publisher)

        if date:
            self.book.add_metadata("DC", "date", date)

        if language:
            self.book.add_metadata("DC", "language", language)
            self.book.set_language(language)

        if isbn:
            clean_isbn = isbn.replace("-", "").replace(" ", "")
            self.book.add_metadata(
                "DC", "identifier", f"isbn:{clean_isbn}", {"id": "isbn"}
            )
            self.book.add_metadata(
                "DC", "identifier", clean_isbn, {"opf:scheme": "ISBN"}
            )

        if series:
            self.book.add_metadata(
                None, "meta", series, {"name": "calibre:series", "content": series}
            )

        if series_index is not None:
            self.book.add_metadata(
                None,
                "meta",
                str(series_index),
                {"name": "calibre:series_index", "content": str(series_index)},
            )

    def _ensure_toc_uids(self):
        """Ensure all TOC items have a UID to satisfy EPUB writer requirements."""
        try:

            def _walk(items, counter=[0]):
                if isinstance(items, (list, tuple)):
                    for it in items:
                        _walk(it, counter)
                else:
                    uid = getattr(items, "uid", None)
                    if not uid:
                        candidate = (
                            getattr(items, "href", None)
                            or getattr(items, "file_name", None)
                            or getattr(items, "title", None)
                        )
                        candidate = candidate or f"nav{counter[0]}"
                        candidate = re.sub(r"[^A-Za-z0-9_-]", "_", str(candidate))
                        if not candidate:
                            candidate = f"nav{counter[0]}"
                        try:
                            items.uid = candidate
                        except (AttributeError, TypeError):
                            pass
                    counter[0] += 1

            _walk(self.book.toc, [0])
        except Exception:  # TOC structure is unpredictable; best-effort, keep broad
            logger.exception("Error ensuring TOC uids")

    def save(self):
        """Save EPUB with updated metadata."""
        self._ensure_toc_uids()
        epub.write_epub(str(self.filepath), self.book)
        logger.info(f"Saved: {self.filepath.name}")
