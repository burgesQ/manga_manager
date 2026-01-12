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


def extract_chapter_number(
    filename: str,
    chapter_pat: Optional[re.Pattern] = None,
    extra_pat: Optional[re.Pattern] = None,
) -> List[Tuple[int, Optional[str]]]:
    base = os.path.basename(filename)
    results: Set[Tuple[int, Optional[str]]] = set()

    # Try extras pattern first when provided; if it matches we assume this is an extra
    if extra_pat is not None:
        m = extra_pat.search(base)
        if m:
            try:
                base_num = int(m.group(1))
                extra = m.group(2)
                results.add((base_num, extra))
                return sorted(results, key=lambda x: (x[0], x[1] if x[1] is not None else ''))
            except Exception:
                pass

    # Then try chapter/main pattern
    if chapter_pat is not None:
        m = chapter_pat.search(base)
        if m:
            try:
                base_num = int(m.group(1))
                results.add((base_num, None))
            except Exception:
                pass

    # Fall back to legacy patterns if none specified
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
