from pathlib import Path
from ebooklib import epub
import logging

logger = logging.getLogger(__name__)


def inject_epub_metadata(
    epub_path: Path,
    title: str,
    authors: list[str] | None = None,
    series: str | None = None,
    series_index: float | None = None,
    isbn: str | None = None,
    language: str = 'ja',
    publisher: str | None = None,
) -> None:
    """Inject metadata into an existing EPUB file."""

    book = epub.read_epub(str(epub_path))

    # Set basic metadata
    book.set_title(title)
    book.set_language(language)

    meta = {
        'title' : title,
        'language': language,
        'authors': authors,
        'isbn': isbn,
        'series': series,
        'series_index': series_index,
        # tags,publisher,publisjed,
        # kobo internal libs ?!
        # calibe tags !?
    }

    if authors:
        # Clear existing authors first
        # DAFUK ?!
        book.metadata.setdefault('http://purl.org/dc/elements/1.1/', {})
        book.metadata['http://purl.org/dc/elements/1.1/']['creator'] = []
        for author in authors:
            book.add_author(author)

    if publisher:
        book.add_metadata('DC', 'publisher', publisher)

    # ISBN - Calibre auto discovery should fine it.
    if isbn:
        book.add_metadata('DC', 'identifier', isbn, {'id': 'isbn'})

    # Series metadata (Calibre-specific)
    if series:
        book.add_metadata(None, 'meta', '', {
            'name': 'calibre:series',
            'content': series
        })

    if series_index is not None:
        book.add_metadata(None, 'meta', '', {
            'name': 'calibre:series_index',
            'content': str(series_index)
        })

    # Write back
    epub.write_epub(str(epub_path), book)
    logger.info(f'Injected metadata into {epub_path}:\n{meta}')
