#!/usr/bin/env python3
"""EPUB Metadata Manager

TODO: clean that up, helpers & refacto.
TODO: loads of tests
TODO: inject calibre' tags (Manga, Seinen, Shonen, Horror, Fiction, Mystery, Fantasy...)
TODO: inject calibre ids (isbn, kobo)
TODO: kobo library collection (Manga, Thriller)
TODO: language
FIXME: ISBN is a calibre id

"""

import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("editor")

try:
    from ebooklib import epub
except ImportError:
    print("Error: ebooklib not installed. Install with: pip install ebooklib")
    sys.exit(1)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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
        except Exception as e:
            raise ValueError(f"Failed to load EPUB {self.filepath}: {e}")

    def has_metadata(self) -> bool:
        """Check if EPUB already has metadata set."""
        # Check if series metadata exists (Calibre format)
        meta = self.book.metadata.get("http://www.idpf.org/2007/opf", {})

        # Look for series metadata
        for item in meta.get("meta", []):
            if isinstance(item, tuple) and len(item) >= 2:
                attrs = item[1] if len(item) > 1 else {}
                if isinstance(attrs, dict):
                    if attrs.get("name") == "calibre:series":
                        return True

        # Also check if it has basic metadata
        dc_meta = self.book.metadata.get("http://purl.org/dc/elements/1.1/", {})
        has_title = bool(dc_meta.get("title"))
        has_creator = bool(dc_meta.get("creator"))

        return has_title and has_creator

    def get_metadata(self) -> dict[str, Any]:
        """Extract current metadata from EPUB."""
        meta = {}

        # Dublin Core metadata
        dc = self.book.metadata.get("http://purl.org/dc/elements/1.1/", {})
        logger.debug(f"meta: {dc}")

        # Title
        if dc.get("title"):
            meta["title"] = (
                dc["title"][0][0]
                if isinstance(dc["title"][0], tuple)
                else dc["title"][0]
            )

        # Creator/Author
        if dc.get("creator"):
            creators = []
            for creator in dc["creator"]:
                name = creator[0] if isinstance(creator, tuple) else creator
                creators.append(name)
            meta["author"] = creators[0] if len(creators) == 1 else creators

        # Publisher
        if dc.get("publisher"):
            meta["publisher"] = (
                dc["publisher"][0][0]
                if isinstance(dc["publisher"][0], tuple)
                else dc["publisher"][0]
            )

        # Date
        if dc.get("date"):
            meta["date"] = (
                dc["date"][0][0] if isinstance(dc["date"][0], tuple) else dc["date"][0]
            )

        # ISBN
        if dc.get("identifier"):
            for identifier in dc["identifier"]:
                id_value = (
                    identifier[0] if isinstance(identifier, tuple) else identifier
                )
                attrs = (
                    identifier[1]
                    if isinstance(identifier, tuple) and len(identifier) > 1
                    else {}
                )
                if isinstance(attrs, dict) and attrs.get("id") == "isbn":
                    meta["isbn"] = id_value
                    break

        # Calibre-specific metadata
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
        language: str = "en-Us",
    ):
        """Set metadata in EPUB file.

        TODO: set calibre tags (genre & other)
        """

        # Set title
        if title:
            self.book.set_title(title)

        # Set author(s)
        if author is not None:
            # Clear existing authors
            dc_ns = "http://purl.org/dc/elements/1.1/"
            if dc_ns not in self.book.metadata:
                self.book.metadata[dc_ns] = {}
            # Always clear first
            self.book.metadata[dc_ns]["creator"] = []
            
            # Add new ones if author is truthy
            if author:
                authors = [author] if isinstance(author, str) else author
                for auth in authors:
                    self.book.add_author(auth)

        # Set publisher
        if publisher:
            self.book.add_metadata("DC", "publisher", publisher)

        # Set date
        if date:
            self.book.add_metadata("DC", "date", date)

        # Set language.
        if date:
            self.book.add_metadata("DC", "language", language)

        # Set ISBN
        if isbn:
            # Clean ISBN
            clean_isbn = isbn.replace("-", "").replace(" ", "")

            # Format 1: identifier avec scheme opf (préféré par Calibre)
            # On utilise 'isbn' comme scheme dans la valeur
            self.book.add_metadata(
                "DC", "identifier", f"isbn:{clean_isbn}", {"id": "isbn"}
            )

            # Format 2: aussi ajouter comme identifiant pur pour compatibilité
            # Certains readers cherchent un identifier sans préfixe
            self.book.add_metadata(
                "DC", "identifier", clean_isbn, {"opf:scheme": "ISBN"}
            )

        # Set series (Calibre format)
        if series:
            self.book.add_metadata(
                None, "meta", series, {"name": "calibre:series", "content": series}
            )

        # Set series index
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
                        # sanitize candidate
                        candidate = re.sub(r"[^A-Za-z0-9_-]", "_", str(candidate))
                        if not candidate:
                            candidate = f"nav{counter[0]}"
                        try:
                            items.uid = candidate
                        except Exception:
                            # Some item types may not allow setting uid; ignore
                            pass
                    counter[0] += 1

            _walk(self.book.toc, [0])
        except Exception:
            logger.exception("Error ensuring TOC uids")

    def save(self):
        """Save EPUB with updated metadata."""
        # Ensure TOC entries have valid uids to avoid lxml TypeError
        self._ensure_toc_uids()
        epub.write_epub(str(self.filepath), self.book)
        logger.info(f"Saved: {self.filepath.name}")


def parse_volume_number(filename: str) -> int | None:
    """Extract volume number from filename.

    Examples:
        'Mashle v01.epub' -> 1
        'Series Name 05.kepub.epub' -> 5
        'Volume 12.epub' -> 12
    """
    patterns = [
        r"v(?:ol)?\.?\s*(\d+)",  # v01, vol 01, vol.01
        r"(?:^|\s)(\d+)(?:\.|$)",  # Just number
        r"volume\s*(\d+)",  # volume 01
    ]

    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def load_yaml_metadata(yaml_path: Path) -> dict:
    """Load metadata from YAML file."""
    with yaml_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def inject_metadata(
    path: Path,
    yaml_path: Path,
    force: bool = False,
    dry_run: bool = False,
):
    """Inject metadata into EPUB files from YAML configuration.
    
    Args:
        path: Either a single EPUB file or a directory containing EPUBs.
        yaml_path: Path to the YAML metadata file.
        force: If True, overwrite existing metadata.
        dry_run: If True, show what would be done without modifying files.
        
    Returns:
        0 on success, 1 on error.
    """

    if not yaml_path.exists():
        logger.error(f"Metadata file not found: {yaml_path}")
        return 1

    epub_files = _get_epub_files(path)
    if not epub_files:
        logger.error(f"No EPUB files found in {path}")
        return 1

    # Load metadata
    metadata = load_yaml_metadata(yaml_path)
    series_name = metadata.get("series")
    author = metadata.get("author")
    publisher_data = metadata.get("publisher", {})
    volumes_data = {v["number"]: v for v in metadata.get("volumes", [])}

    logger.info(f"Found {len(epub_files)} EPUB file(s)")
    logger.info(f"Series: {series_name}")
    logger.info(f"Author: {author}")
    logger.info(f"Publisher: {publisher_data}")

    success_count = 0
    skip_count = 0
    error_count = 0

    for epub_file in epub_files:
        try:
            # Parse volume number
            vol_num = parse_volume_number(epub_file.name)
            if vol_num is None:
                logger.warning(f"Could not parse volume number from: {epub_file.name}")
                continue

            vol_data = volumes_data.get(vol_num)
            if not vol_data:
                logger.warning(f"No metadata for volume {vol_num} in YAML")
                continue

            logger.info(f"\nProcessing: {epub_file.name} (Volume {vol_num})")

            # Load EPUB
            epub_meta = EPUBMetadata(epub_file)

            # Check if has metadata
            if epub_meta.has_metadata() and not force:
                logger.info(
                    f"  Skipping (already has metadata, use --force to overwrite)"
                )
                skip_count += 1
                continue

            #if dry_run:
            #    logger.info(f"  [DRY RUN] Would inject metadata for volume {vol_num}")
            #    success_count += 1
            #    continue

            # Prepare metadata
            title = vol_data.get("title")
            if not title:
                title = f"{series_name} v{vol_num:02d}"

            # TODO: parametrize language from metadata.yaml

            # Use English metadata if available, otherwise Japanese
            locale_data = vol_data.get("english", {})
            release_date = locale_data.get("release_date")
            isbn = locale_data.get("isbn")

            # Use English publisher if available
            publisher = publisher_data.get("english")

            # if dry_run:
            #     logger.info(
            #         f"  [DRY RUN] Would inject metadata for volume {float(vol_num)}"
            #     )
            #     logger.info(f"  [DRY RUN] Title {title}")
            #     logger.info(f"  [DRY RUN] Release date {release_date}")
            #     logger.info(f"  [DRY RUN] ISBN {isbn}")

            #     success_count += 1
            #     continue

            # Inject metadata
            if dry_run:
                logger.info(
                    f"  [DRY RUN] Would inject metadata for volume {float(vol_num)}"
                )
            else:
                epub_meta.set_metadata(
                    title=title,
                    author=author,
                    series=series_name,
                    series_index=float(vol_num),
                    date=release_date,
                    isbn=isbn,
                    publisher=publisher,
                    language="en-US",
                    # TODO: better injection
                )

                # # Debug: log TOC items before saving to help diagnose None uid
                # try:
                #     logger.debug(f"  TOC: {epub_meta.book.toc!r}")
                #     for it in epub_meta.book.toc:
                #         uid = getattr(it, "uid", None)
                #         logger.debug(f"  TOC item: type={type(it)} uid={uid} repr={it!r}")
                # except Exception:
                #     logger.exception("  Error while logging TOC")

                # Save
                epub_meta.save()

            logger.info(f"  ✓ Injected metadata:")
            logger.info(f"    Title: {title}")
            logger.info(f"    Series: {series_name} #{vol_num}")
            logger.info(f"    Author: {author}")
            logger.info(f"    Date: {release_date}")
            logger.info(f"    ISBN: {isbn}")

            success_count += 1

        except Exception:
            logger.exception(f"  ✗ Error processing {epub_file.name}:")
            error_count += 1

    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total files:     {len(epub_files)}")
    logger.info(f"✓ Processed:     {success_count}")
    logger.info(f"⊘ Skipped:       {skip_count}")
    logger.info(f"✗ Errors:        {error_count}")
    logger.info("=" * 60)

    return 1 if error_count > 0 else 0


def dump_metadata(path: Path, output_path: Path | None = None):
    """Dump metadata from EPUB files to YAML.
    
    Args:
        path: Either a single EPUB file or a directory containing EPUBs.
        output_path: Optional path to save the YAML output.
        
    Returns:
        0 on success, 1 on error.
    """

    epub_files = _get_epub_files(path)
    if not epub_files:
        logger.error(f"No EPUB files found in {path}")
        return 1

    logger.info(f"Found {len(epub_files)} EPUB file(s)")

    volumes = []
    series_name = None
    author = None
    publisher = None

    for epub_file in epub_files:
        try:
            vol_num = parse_volume_number(epub_file.name)

            logger.info(f"Reading: {epub_file.name}")

            epub_meta = EPUBMetadata(epub_file)
            meta = epub_meta.get_metadata()

            # Extract common info
            if not series_name and meta.get("series"):
                series_name = meta["series"]
            if not author and meta.get("author"):
                author = meta["author"]
            if not publisher and meta.get("publisher"):
                publisher = meta["publisher"]

            # Volume data
            vol_data = {
                "number": vol_num if vol_num else len(volumes) + 1,
            }

            if meta.get("title"):
                vol_data["title"] = meta["title"]

            if meta.get("date") or meta.get("isbn"):
                vol_data["metadata"] = {}
                if meta.get("date"):
                    vol_data["metadata"]["release_date"] = meta["date"]
                if meta.get("isbn"):
                    vol_data["metadata"]["isbn"] = meta["isbn"]

            volumes.append(vol_data)

        except Exception as e:
            logger.error(f"Error reading {epub_file.name}: {e}")

    # Build YAML structure
    output_data = {
        "series": series_name or "Unknown Series",
        "author": author or "Unknown Author",
    }

    if publisher:
        output_data["publisher"] = publisher

    output_data["volumes"] = sorted(volumes, key=lambda v: v["number"])

    # Output
    if output_path:
        with output_path.open("w", encoding="utf-8") as f:
            yaml.dump(
                output_data,
                f,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            )
        logger.info(f"\n✓ Saved to: {output_path}")
    else:
        print("\n" + "=" * 60)
        print(
            yaml.dump(
                output_data,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            )
        )
        print("=" * 60)

    return 0

def _get_epub_files(path: Path) -> list[Path]:
    """Get EPUB files from either a single file or a directory.
    
    Args:
        path: Either a single EPUB file or a directory containing EPUB files.
        
    Returns:
        A list of EPUB file paths.
    """
    if path.is_file():
        if path.suffix.lower() in (".epub", ".kepub"):
            return [path]
        else:
            logger.warning(f"File is not an EPUB: {path}")
            return []
    elif path.is_dir():
        epub_files = sorted(path.glob("*.epub"))
        epub_files += sorted(path.glob("*.kepub.epub"))
        # Remove duplicates
        return list(dict.fromkeys(epub_files))
    else:
        logger.error(f"Path does not exist: {path}")
        return []


def clear_metadata(path: Path, dry_run: bool = False) -> int:
    """Clear all metadata from EPUB files.
    
    Args:
        path: Either a single EPUB file or a directory containing EPUBs.
        dry_run: If True, show what would be done without modifying files.
        
    Returns:
        0 on success, 1 on error.
    """
    epub_files = _get_epub_files(path)
    
    if not epub_files:
        logger.warning(f"No EPUB files found in {path}")
        return 0
    
    logger.info(f"Found {len(epub_files)} EPUB file(s)")
    
    success_count = 0
    error_count = 0
    
    for epub_file in epub_files:
        try:
            logger.info(f"Processing: {epub_file.name}")
            
            if dry_run:
                logger.info(f"  [DRY RUN] Would clear metadata from {epub_file.name}")
                success_count += 1
                continue
            
            # Load EPUB
            epub_meta = EPUBMetadata(epub_file)
            
            # Clear major metadata fields by setting them to empty values
            epub_meta.set_metadata(
                title="",
                author=[],  # empty list triggers author clearing
                series="",
                series_index=None,
                date="",
                isbn="",
                publisher="",
            )
            
            # Save changes
            epub_meta.save()
            logger.info(f"  ✓ Cleared metadata from {epub_file.name}")
            success_count += 1
            
        except Exception as e:
            logger.error(f"  ✗ Error processing {epub_file.name}: {e}")
            error_count += 1
    
    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total files:     {len(epub_files)}")
    logger.info(f"✓ Processed:     {success_count}")
    logger.info(f"✗ Errors:        {error_count}")
    logger.info("=" * 60)
    
    return 1 if error_count > 0 else 0