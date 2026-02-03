"""Core utilities: parsing, filename matching, and file discovery."""

from __future__ import annotations

import os
import re
import zipfile
from typing import Dict, List, Optional, Set, Tuple, TypeAlias
from .types_ import ChapterMatch, ChapterMapping

CHAPTER_PATTERNS = [
    re.compile(r"(?i)chapter[\s._-]*0*([0-9]+)"),
    re.compile(r"(?i)ch(?:\.|apter)?[\s._-]*0*([0-9]+)"),
]


def parse_range(text: str) -> List[int]:
    """Parse a textual chapter range into a sorted list of integers.

    Accepts commas and inclusive ranges expressed with `..`.

    Examples:
    >>> parse_range('1,3,5..7')
    [1, 3, 5, 6, 7]
    >>> parse_range('2..4')
    [2, 3, 4]

    Raises ValueError when an end is smaller than the start.
    """
    parts = [p.strip() for p in text.split(",") if p.strip()]
    nums: Set[int] = set()
    for p in parts:
        if ".." in p:
            a, b = p.split("..", 1)
            a_i = int(a)
            b_i = int(b)
            if b_i < a_i:
                raise ValueError(f"Invalid range {p}: end < start")
            nums.update(range(a_i, b_i + 1))
        else:
            nums.add(int(p))
    return sorted(nums)


def _match_extra(base: str, extra_pat: Optional[re.Pattern]) -> Optional[ChapterMatch]:
    """Return ChapterMatch if the `extra_pat` matches the filename base."""
    # noqa: E501
    if extra_pat is None:
        return None
    m = extra_pat.search(base)
    if not m:
        return None
    try:
        base_num = int(m.group(1))
        extra = m.group(2)
        return ChapterMatch(base=base_num, extra=extra)
    except Exception:
        return None


def _match_chapter(base: str, chapter_pat: Optional[re.Pattern]) -> Optional[int]:
    """Return base_num if `chapter_pat` matches the filename base."""
    # noqa: E501
    if chapter_pat is None:
        return None
    m = chapter_pat.search(base)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def extract_chapter_number(
    filename: str,
    chapter_pat: Optional[re.Pattern] = None,
    extra_pat: Optional[re.Pattern] = None,
) -> List[ChapterMatch]:
    """Extract chapter numbers and optional extra suffixes from a filename.

    Behavior summary:
    - If `extra_pat` is provided and matches, the file is treated as an extra.
    - Otherwise, if `chapter_pat` matches, a main chapter is returned.
    - If neither pattern matches, a set of legacy patterns is used as fallback.

    Returns a list of ChapterMatch NamedTuples where extra is None for main chapters.
    """  # noqa: E501
    base = os.path.basename(filename)
    results: Set[ChapterMatch] = set()

    # Extra pattern takes precedence when provided: treat as an extra and return it
    extra_match = _match_extra(base, extra_pat)
    if extra_match is not None:
        results.add(extra_match)
        return sorted(
            results, key=lambda x: (x.base, x.extra if x.extra is not None else "")
        )

    # Then try chapter/main pattern
    chapter_match = _match_chapter(base, chapter_pat)
    if chapter_match is not None:
        results.add(ChapterMatch(base=chapter_match, extra=None))

    # Fall back to legacy patterns if none found
    if not results:
        legacy_patterns = [
            re.compile(r"(?i)chapter[\s._-]*0*([0-9]+)(?:\.([0-9]+))?"),
            re.compile(r"(?i)ch(?:\.|apter)?[\s._-]*0*([0-9]+)(?:\.([0-9]+))?"),
        ]
        for pat in legacy_patterns:
            m = pat.search(base)
            if m:
                try:
                    base_num = int(m.group(1))
                    extra = m.group(2)
                    results.add(ChapterMatch(base=base_num, extra=extra))
                except Exception:
                    continue

    # Sort by base then by extra (treat None as empty string for sorting)
    return sorted(
        results,
        key=lambda x: (x.base, x.extra if x.extra is not None else ""),  # noqa: E501
    )


def find_cbz_files(root: str) -> List[str]:
    """Return a list of full paths to `.cbz` files found in `root`.

    Args:
        root: Path to directory to scan for `.cbz` files.

    Returns:
        List[str]: Absolute or relative paths (matching how `root` is passed) to
        files whose names end with `.cbz` (case-insensitive).

    Raises:
        OSError: If scanning the directory fails (propagates the underlying
        filesystem exception to the caller).
    """
    files: List[str] = []
    for entry in os.listdir(root):
        if entry.lower().endswith(".cbz") and os.path.isfile(os.path.join(root, entry)):
            files.append(os.path.join(root, entry))
    return files


def map_chapters_to_files(
    cbz_files: List[str],
) -> ChapterMapping:
    """Map chapter numbers to their matching archives.

    Returns a mapping {base: {'mains': [...], 'extras': [...]}}.

    Example:
    >>> m = map_chapters_to_files(['Chapter 1.cbz', 'Chapter 1.5.cbz'])
    >>> sorted(m.keys())
    [1]
    >>> m[1]['mains'][0][1]
    'Chapter 1.cbz'
    >>> m[1]['extras'][0][0]
    '5'
    """
    mapping: Dict[int, Dict[str, List[Tuple[Optional[str], str]]]] = {}
    for p in cbz_files:
        matches = extract_chapter_number(p)
        for m in matches:
            base_num = m.base
            extra = m.extra
            entry = mapping.setdefault(base_num, {"mains": [], "extras": []})
            if extra is None:
                entry["mains"].append((None, p))
            else:
                entry["extras"].append((extra, p))
    return mapping


def has_comicinfo(cbz_path: str) -> bool:
    """Check whether a `.cbz` archive contains a `ComicInfo.xml` file.

    Args:
        cbz_path: Path to the `.cbz` file to inspect.

    Returns:
        True if a file named (case-insensitive) `ComicInfo.xml` exists in the
        archive, otherwise False.

    Notes:
        - If the given file is not a valid zip archive, this function returns
          False (the error is handled internally). Callers may treat False as
          "missing or invalid ComicInfo.xml" and react accordingly.
    """
    try:
        with zipfile.ZipFile(cbz_path, "r") as z:
            for n in z.namelist():
                if n.lower().endswith("comicinfo.xml"):
                    return True
    except zipfile.BadZipFile:
        return False
    return False


def format_volume_dir(dest: str, serie: str, volume: int) -> str:
    """Return the canonical volume directory path.

    Example:
    >>> format_volume_dir('/tmp', 'Berserk', 1)
    '/tmp/Berserk v01'
    """
    return os.path.join(dest, f"{serie} v{volume:02d}")
