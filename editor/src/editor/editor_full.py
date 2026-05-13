"""EPUB Metadata Manager — high-level operations (inject / dump / clear)."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from .epub_metadata import EPUBMetadata  # noqa: F401 — re-exported for callers
from .exit_codes import ERROR, SUCCESS

logger = logging.getLogger(__name__)


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


def _inject_single(
    epub_file: Path,
    vol_num: int,
    vol_data: dict,
    *,
    series_name: str | None,
    author: str | None,
    publisher: str | None,
    language: str,
    tags: list[str] | None,
    locale: str,
    force: bool,
    dry_run: bool,
) -> str:
    """Inject metadata into one EPUB file.

    Returns ``"ok"``, ``"skip"`` (already has metadata), or ``"err"``.
    """
    try:
        epub_meta = EPUBMetadata(epub_file)

        if epub_meta.has_metadata() and not force:
            logger.info("  Skipping (already has metadata, use --force to overwrite)")
            return "skip"

        title = vol_data.get("title") or f"{series_name} v{vol_num:02d}"
        vol_language = vol_data.get("language", language)
        locale_data = vol_data.get(locale, {}) or {}
        release_date = locale_data.get("release_date")
        isbn = locale_data.get("isbn")

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
                language=vol_language,
                tags=tags,
            )
            epub_meta.save()

        logger.info("  ✓ Injected metadata:")
        logger.info(f"    Title: {title}")
        logger.info(f"    Series: {series_name} #{vol_num}")
        logger.info(f"    Author: {author}")
        logger.info(f"    Date: {release_date}")
        logger.info(f"    ISBN: {isbn}")
        logger.info(f"    Tags: {tags}")
        return "ok"

    except Exception:  # per-file guard: continue processing remaining files
        logger.exception(f"  ✗ Error processing {epub_file.name}:")
        return "err"


_LOCALE_LANGUAGE: dict[str, str] = {
    "english": "en-US",
    "japanese": "ja",
    "french": "fr-FR",
}


def inject_metadata(
    path: Path,
    yaml_path: Path,
    force: bool = False,
    dry_run: bool = False,
    locale: str = "english",
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
        return ERROR

    epub_files = _get_epub_files(path)
    if not epub_files:
        logger.error(f"No EPUB files found in {path}")
        return ERROR

    metadata = load_yaml_metadata(yaml_path)
    series_name = metadata.get("series")
    author = metadata.get("author")
    publisher_data = metadata.get("publisher") or {}
    tags: list[str] | None = metadata.get("genre") or None
    language = metadata.get("language") or _LOCALE_LANGUAGE.get(locale, "en-US")
    volumes_data = {v["number"]: v for v in metadata.get("volumes", [])}
    publisher = (
        publisher_data.get(locale)
        if isinstance(publisher_data, dict)
        else publisher_data
    )

    logger.info(f"Found {len(epub_files)} EPUB file(s)")
    logger.info(f"Series: {series_name}")
    logger.info(f"Author: {author}")
    logger.info(f"Locale: {locale} → publisher={publisher}, language={language}")
    logger.info(f"Tags: {tags}")

    success_count = 0
    skip_count = 0
    error_count = 0

    for epub_file in epub_files:
        vol_num = parse_volume_number(epub_file.name)
        if vol_num is None:
            logger.warning(f"Could not parse volume number from: {epub_file.name}")
            continue

        vol_data = volumes_data.get(vol_num)
        if not vol_data:
            logger.warning(f"No metadata for volume {vol_num} in YAML")
            continue

        logger.info(f"\nProcessing: {epub_file.name} (Volume {vol_num})")
        result = _inject_single(
            epub_file,
            vol_num,
            vol_data,
            series_name=series_name,
            author=author,
            publisher=publisher,
            language=language,
            tags=tags,
            locale=locale,
            force=force,
            dry_run=dry_run,
        )
        if result == "ok":
            success_count += 1
        elif result == "skip":
            skip_count += 1
        else:
            error_count += 1

    logger.info(f"\n{'=' * 60}")
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total files:     {len(epub_files)}")
    logger.info(f"✓ Processed:     {success_count}")
    logger.info(f"⊘ Skipped:       {skip_count}")
    logger.info(f"✗ Errors:        {error_count}")
    logger.info("=" * 60)

    return ERROR if error_count > 0 else SUCCESS


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
        return ERROR

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

            if not series_name and meta.get("series"):
                series_name = meta["series"]
            if not author and meta.get("author"):
                author = meta["author"]
            if not publisher and meta.get("publisher"):
                publisher = meta["publisher"]

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

        except Exception as e:  # per-file loop guard: continue dumping remaining files
            logger.error(f"Error reading {epub_file.name}: {e}")

    output_data = {
        "series": series_name or "Unknown Series",
        "author": author or "Unknown Author",
    }

    if publisher:
        output_data["publisher"] = publisher

    output_data["volumes"] = sorted(volumes, key=lambda v: v["number"])

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

    return SUCCESS


def _get_epub_files(path: Path) -> list[Path]:
    """Get EPUB files from either a single file or a directory."""
    if path.is_file():
        if path.suffix.lower() in (".epub", ".kepub"):
            return [path]
        else:
            logger.warning(f"File is not an EPUB: {path}")
            return []
    elif path.is_dir():
        epub_files = sorted(path.glob("*.epub"))
        epub_files += sorted(path.glob("*.kepub.epub"))
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
        return SUCCESS

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

            epub_meta = EPUBMetadata(epub_file)
            epub_meta.set_metadata(
                title="",
                author=[],
                series="",
                series_index=None,
                date="",
                isbn="",
                publisher="",
            )
            epub_meta.save()
            logger.info(f"  ✓ Cleared metadata from {epub_file.name}")
            success_count += 1

        except Exception as e:  # per-file loop guard: continue clearing remaining files
            logger.error(f"  ✗ Error processing {epub_file.name}: {e}")
            error_count += 1

    logger.info(f"\n{'=' * 60}")
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total files:     {len(epub_files)}")
    logger.info(f"✓ Processed:     {success_count}")
    logger.info(f"✗ Errors:        {error_count}")
    logger.info("=" * 60)

    return ERROR if error_count > 0 else SUCCESS
