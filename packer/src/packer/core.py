"""Core utilities: parsing, filename matching, and file discovery."""
from __future__ import annotations

import os
import re
import zipfile
from pathlib import PurePosixPath
from typing import Dict, List, Optional, Set, Tuple

CHAPTER_PATTERNS = [
    re.compile(r'(?i)chapter[\s._-]*0*([0-9]+)'),
    re.compile(r'(?i)ch(?:\.|apter)?[\s._-]*0*([0-9]+)'),
]


def parse_range(text: str) -> List[int]:
    parts = [p.strip() for p in text.split(',') if p.strip()]
    nums: Set[int] = set()
    for p in parts:
        if '..' in p:
            a, b = p.split('..', 1)
            a_i = int(a)
            b_i = int(b)
            if b_i < a_i:
                raise ValueError(f"Invalid range {p}: end < start")
            nums.update(range(a_i, b_i + 1))
        else:
            nums.add(int(p))
    return sorted(nums)


def _match_extra(base: str, extra_pat: Optional[re.Pattern]) -> Optional[tuple]:
    """Return (base_num, extra) if the `extra_pat` matches the filename base.

    >>> _match_extra('Ch.013.5.cbz', re.compile(r'(?i)ch(?:\\.|apter)?[\\s._-]*0*([0-9]+)\\.([0-9]+)'))
    (13, '5')
    >>> _match_extra('Chap 16.2.cbz', re.compile(r'(?i)chap(?:\\.|ter)?[\\s._-]*0*([0-9]+)\\.([0-9]+)'))
    (16, '2')
    >>> _match_extra('Chapter 1.cbz', re.compile(r'(?i)ch(?:\\.|apter)?[\\s._-]*0*([0-9]+)\\.([0-9]+)')) is None
    True
    """
    if extra_pat is None:
        return None
    m = extra_pat.search(base)
    if not m:
        return None
    try:
        base_num = int(m.group(1))
        extra = m.group(2)
        return base_num, extra
    except Exception:
        return None


def _match_chapter(base: str, chapter_pat: Optional[re.Pattern]) -> Optional[int]:
    """Return base_num if `chapter_pat` matches the filename base.

    >>> _match_chapter('Ch.013.cbz', re.compile(r'(?i)ch(?:\\.|apter)?[\\s._-]*0*([0-9]+)'))
    13
    >>> _match_chapter('Chapter 004 Name.cbz', re.compile(r'(?i)chapter[\\s._-]*0*([0-9]+)'))
    4
    >>> _match_chapter('NoMatch.cbz', re.compile(r'(?i)ch(?:\\.|apter)?[\\s._-]*0*([0-9]+)')) is None
    True
    """
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
) -> List[Tuple[int, Optional[str]]]:
    """Extract chapter numbers and optional extra suffixes from a filename.

    Behavior summary:
    - If `extra_pat` is provided and matches, the file is treated as an extra and
      the function returns a single entry for that extra (base, extra).
    - Otherwise, if `chapter_pat` matches, a main chapter (base, None) is returned.
    - If neither pattern is provided or matches, a set of legacy patterns is used
      as a fallback.

    Examples:

    >>> extract_chapter_number('Ch.013.5.cbz', re.compile(r'(?i)ch(?:\\.|apter)?[\\s._-]*0*([0-9]+)'), re.compile(r'(?i)ch(?:\\.|apter)?[\\s._-]*0*([0-9]+)\\.([0-9]+)'))
    [(13, '5')]
    >>> extract_chapter_number('Chap 16.cbz', re.compile(r'(?i)chap(?:\\.|ter)?[\\s._-]*0*([0-9]+)'), re.compile(r'(?i)chap(?:\\.|ter)?[\\s._-]*0*([0-9]+)\\.([0-9]+)'))
    [(16, None)]
    >>> extract_chapter_number('Chapter 2.cbz')
    [(2, None)]

    Returns a list of (base, extra) tuples where extra is None for main chapters.
    """
    base = os.path.basename(filename)
    results: Set[Tuple[int, Optional[str]]] = set()

    # Extra pattern takes precedence when provided: treat as an extra and return it
    extra_match = _match_extra(base, extra_pat)
    if extra_match is not None:
        base_num, extra = extra_match
        results.add((base_num, extra))
        return sorted(results, key=lambda x: (x[0], x[1] if x[1] is not None else ''))

    # Then try chapter/main pattern
    chapter_match = _match_chapter(base, chapter_pat)
    if chapter_match is not None:
        results.add((chapter_match, None))

    # Fall back to legacy patterns if none found
    if not results:
        legacy_patterns = [
            re.compile(r'(?i)chapter[\s._-]*0*([0-9]+)(?:\.([0-9]+))?'),
            re.compile(r'(?i)ch(?:\.|apter)?[\s._-]*0*([0-9]+)(?:\.([0-9]+))?'),
        ]
        for pat in legacy_patterns:
            m = pat.search(base)
            if m:
                try:
                    base_num = int(m.group(1))
                    extra = m.group(2)
                    results.add((base_num, extra))
                except Exception:
                    continue

    # Sort by base then by extra (treat None as empty string for sorting)
    return sorted(results, key=lambda x: (x[0], x[1] if x[1] is not None else ''))


def find_cbz_files(root: str) -> List[str]:
    files: List[str] = []
    for entry in os.listdir(root):
        if entry.lower().endswith('.cbz') and os.path.isfile(os.path.join(root, entry)):
            files.append(os.path.join(root, entry))
    return files


def map_chapters_to_files(cbz_files: List[str]) -> Dict[int, Dict[str, List[Tuple[Optional[str], str]]]]:
    mapping: Dict[int, Dict[str, List[Tuple[Optional[str], str]]]] = {}
    for p in cbz_files:
        matches = extract_chapter_number(p)
        for base_num, extra in matches:
            entry = mapping.setdefault(base_num, {'mains': [], 'extras': []})
            if extra is None:
                entry['mains'].append((None, p))
            else:
                entry['extras'].append((extra, p))
    return mapping


def has_comicinfo(cbz_path: str) -> bool:
    try:
        with zipfile.ZipFile(cbz_path, 'r') as z:
            for n in z.namelist():
                if n.lower().endswith('comicinfo.xml'):
                    return True
    except zipfile.BadZipFile:
        return False
    return False


def format_volume_dir(dest: str, serie: str, volume: int) -> str:
    return os.path.join(dest, f"{serie} v{volume:02d}")
