    #!/usr/bin/env python3
"""CLI for the packer utility.

Implements:
- argument parsing (`argparse`)
- chapter-range parsing
- discovery of `.cbz` files matching chapter numbers (several patterns)
- validation that each `.cbz` contains `ComicInfo.xml`
- creation of volume dir and chapter dirs, moving archives there

Extraction of archive contents is intentionally left as TODO: the code will
create chapter directories and then raise `ExtractionNotImplementedError` so
you can inspect the produced layout before we implement extraction rules.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import os
import re
import shutil
import sys
import zipfile
from pathlib import PurePosixPath
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Set, Tuple


class ExtractionNotImplementedError(RuntimeError):
    pass


def parse_range(text: str) -> List[int]:
    """Parse chapter-range like "1..10", "1,3,5..8" into sorted unique ints."""
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


CHAPTER_PATTERNS = [
    re.compile(r'(?i)chapter[\s._-]*0*([0-9]+)'),
    re.compile(r'(?i)ch(?:\.|apter)?[\s._-]*0*([0-9]+)'),
]


from typing import Optional


def extract_chapter_number(filename: str) -> List[Tuple[int, Optional[str]]]:
    """Return list of (base_chapter, extra_suffix) pairs found in `filename`.

    Examples:
      'Chapter 13.cbz' -> [(13, None)]
      'Ch.013.5.cbz' -> [(13, '5')]

    Uses patterns that optionally capture an extra suffix (e.g. '.5'). Duplicates
    are removed.
    """
    base = os.path.basename(filename)
    results: Set[Tuple[int, Optional[str]]] = set()
    # Accept patterns that capture optional extra part
    extra_patterns = [
        re.compile(r'(?i)chapter[\s._-]*0*([0-9]+)(?:\.([0-9]+))?'),
        re.compile(r'(?i)ch(?:\.|apter)?[\s._-]*0*([0-9]+)(?:\.([0-9]+))?'),
    ]
    for pat in extra_patterns:
        m = pat.search(base)
        if m:
            try:
                base_num = int(m.group(1))
                extra = m.group(2)
                results.add((base_num, extra))
            except Exception:
                continue
    return sorted(results)


def find_cbz_files(root: str) -> List[str]:
    files: List[str] = []
    for entry in os.listdir(root):
        if entry.lower().endswith('.cbz') and os.path.isfile(os.path.join(root, entry)):
            files.append(os.path.join(root, entry))
    return files


def map_chapters_to_files(cbz_files: Sequence[str]) -> Dict[int, Dict[str, List[Tuple[Optional[str], str]]]]:
    """Map detected base chapters to dict with 'mains' and 'extras'.

    Result format:
      { 13: { 'mains': [file], 'extras': [('5', file2), ...] }, ... }

    A 'main' is an archive without an extra suffix (e.g. Chapter 13). Extras have
    a suffix (e.g. 13.5 -> suffix '5')."""
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


@dataclass
class Config:
    path: str
    dest: str
    serie: str
    volume: int
    chapter_range: List[int]
    nb_worker: int = 1
    dry_run: bool = False
    verbose: bool = False
    force: bool = False


def format_volume_dir(dest: str, serie: str, volume: int) -> str:
    return os.path.join(dest, f"{serie} v{volume:02d}")


def process_one(chapter_id: str, src_file: str, cfg: Config) -> Tuple[str, str]:
    """Process one chapter (main or extra): validate comicinfo, move file, create chapter dir.

    chapter_id is a string: e.g. '13' for main, '13.5' for an extra. The chapter
    directory will be named `Chapter {base:03d}` for main or `Chapter {base:03d}.{extra}` for extras.
    """
    if cfg.verbose:
        print(f"[worker] start chapter={chapter_id} file={src_file}")

    # Validate comicinfo
    if cfg.verbose:
        print(f"[worker] verifying ComicInfo.xml in {src_file}")
    if not has_comicinfo(src_file):
        raise RuntimeError(f"Missing ComicInfo.xml in {src_file}")

    volume_dir = format_volume_dir(cfg.dest, cfg.serie, cfg.volume)
    if not os.path.exists(volume_dir):
        if cfg.verbose:
            print(f"[worker] creating volume dir: {volume_dir}")
        if not cfg.dry_run:
            os.makedirs(volume_dir, exist_ok=True)
        elif cfg.verbose:
            print(f"[dry-run] mkdir {volume_dir}")
    else:
        if cfg.verbose:
            print(f"[worker] volume dir exists: {volume_dir}")

    # Move archive
    dest_archive = os.path.join(volume_dir, os.path.basename(src_file))
    if cfg.dry_run:
        if cfg.verbose:
            print(f"[dry-run] mv {src_file} -> {dest_archive}")
    else:
        if cfg.verbose:
            print(f"[worker] moving archive to {dest_archive}")
        shutil.move(src_file, dest_archive)

    # Determine chapter dir name
    if '.' in chapter_id:
        base_part, extra_part = chapter_id.split('.', 1)
        chapter_dir_name = f"Chapter {int(base_part):03d}.{extra_part}"
    else:
        chapter_dir_name = f"Chapter {int(chapter_id):03d}"
    chapter_dir = os.path.join(volume_dir, chapter_dir_name)

    if os.path.exists(chapter_dir):
        if cfg.force:
            if cfg.verbose:
                print(f"[worker] force-remove existing chapter dir: {chapter_dir}")
            shutil.rmtree(chapter_dir)
            if not cfg.dry_run:
                os.makedirs(chapter_dir, exist_ok=True)
            elif cfg.verbose:
                print(f"[dry-run] mkdir {chapter_dir}")
        else:
            # According to rules: warn and skip
            print(f"[warn] chapter dir exists, skipping: {chapter_dir}")
            return chapter_id, dest_archive
    else:
        if cfg.verbose:
            print(f"[worker] creating chapter dir: {chapter_dir}")
        if not cfg.dry_run:
            os.makedirs(chapter_dir, exist_ok=True)
        elif cfg.verbose:
            print(f"[dry-run] mkdir {chapter_dir}")

    # Safe extraction (prevent path traversal). In dry-run, inspect the original src file but do not extract
    # or depend on the moved `dest_archive` which doesn't exist in dry-run mode.
    try:
        archive_for_inspection = src_file if cfg.dry_run else dest_archive
        with zipfile.ZipFile(archive_for_inspection, 'r') as z:
            names = z.namelist()
            for member in names:
                parts = PurePosixPath(member).parts
                if '..' in parts or member.startswith('/') or member.startswith('\\'):
                    raise RuntimeError(f"Unsafe path in archive: {member}")
            if cfg.dry_run:
                if cfg.verbose:
                    print(f"[dry-run] extract {archive_for_inspection} -> {chapter_dir}")
            else:
                z.extractall(chapter_dir)
                if cfg.verbose:
                    print(f"[worker] extracted {dest_archive} -> {chapter_dir}")
    except zipfile.BadZipFile:
        raise RuntimeError(f"Bad zip file: {archive_for_inspection}")

    return chapter_id, dest_archive


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Pack .cbz chapters into volume directories")
    p.add_argument('--path', required=True, help='path to root directory containing .cbz files')
    p.add_argument('--dest', default=None, help='destination root (defaults to --path)')
    p.add_argument('--serie', required=True, help='series name used to name the volume directory')
    p.add_argument('--volume', required=True, type=int, help='volume number to create')
    p.add_argument('--chapter-range', required=True, help='chapter range, e.g. "1..12" or "1,3,5..8"')
    p.add_argument('--nb-worker', type=int, default=1, help='number of workers (default 1)')
    p.add_argument('--dry-run', action='store_true', help='simulate actions')
    p.add_argument('--verbose', action='store_true', help='verbose logging')
    p.add_argument('--force', action='store_true', help='overwrite chapter dirs if exist')

    args = p.parse_args(argv)
    dest = args.dest if args.dest else args.path
    try:
        chapters = parse_range(args.chapter_range)
    except Exception as e:
        print(f"Invalid chapter range: {e}", file=sys.stderr)
        return 2

    cfg = Config(
        path=args.path,
        dest=dest,
        serie=args.serie,
        volume=args.volume,
        chapter_range=chapters,
        nb_worker=args.nb_worker,
        dry_run=args.dry_run,
        verbose=args.verbose,
        force=args.force,
    )

    cbz_files = find_cbz_files(cfg.path)
    if cfg.verbose:
        print(f"[info] scanning path={cfg.path}")
        print(f"[info] found {len(cbz_files)} .cbz files")
        for f in cbz_files:
            print(f"[info]   {f}")
    mapping = map_chapters_to_files(cbz_files)
    if cfg.verbose:
        print(f"[info] chapter mapping summary:")
        for k in sorted(mapping.keys()):
            print(f"[info]   chapter {k}: {mapping[k]}")

    # Validate presence & uniqueness of main chapters (extras are optional)
    if cfg.verbose:
        print(f"[info] validating requested chapters: {cfg.chapter_range}")
    for c in cfg.chapter_range:
        entry = mapping.get(c)
        if not entry or (not entry.get('mains') and not entry.get('extras')):
            print(f"[error] missing chapter {c}", file=sys.stderr)
            return 3
        if len(entry.get('mains', [])) > 1:
            mains = [p for (_, p) in entry['mains']]
            print(f"[error] multiple archives match chapter {c}: {mains}", file=sys.stderr)
            return 4

    # Prepare tasks: include main archive for each requested chapter and any extras found
    tasks: List[Tuple[str, str]] = []  # (chapter_id, file)
    for c in cfg.chapter_range:
        entry = mapping.get(c, {'mains': [], 'extras': []})
        # Prefer the single main archive if present
        if entry.get('mains'):
            _, main_file = entry['mains'][0]
            tasks.append((str(c), main_file))
        else:
            # No main but extras exist: still process extras
            pass
        for extra_suffix, extra_file in entry.get('extras', []):
            tasks.append((f"{c}.{extra_suffix}", extra_file))

    if cfg.verbose:
        print("[info] planned tasks:")
        for cid, f in tasks:
            print(f"[info]  chapter {cid} -> {f}")

    # Ensure volume directory exists (main thread creates it to avoid races)
    volume_dir = format_volume_dir(cfg.dest, cfg.serie, cfg.volume)
    if not os.path.exists(volume_dir):
        if cfg.verbose:
            print(f"[info] creating volume dir: {volume_dir}")
        if not cfg.dry_run:
            os.makedirs(volume_dir, exist_ok=True)
        elif cfg.verbose:
            print(f"[dry-run] mkdir {volume_dir}")
    else:
        if cfg.verbose:
            print(f"[info] volume dir exists: {volume_dir}")

    # Process tasks using threads (I/O-bound): each worker handles one chapter (mv -> mkdir chapter -> unpack)
    if cfg.nb_worker > 1:
        if cfg.verbose:
            print(f"[info] Using ThreadPoolExecutor with {cfg.nb_worker} workers")
        with concurrent.futures.ThreadPoolExecutor(max_workers=cfg.nb_worker) as ex:
            futures = [ex.submit(process_one, c, f, cfg) for c, f in tasks]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    res = fut.result()
                    if cfg.verbose:
                        print(f"Processed: {res}")
                except ExtractionNotImplementedError as e:
                    print(f"[TODO] {e}")
                    return 5
                except Exception as e:
                    print(f"[error] {e}", file=sys.stderr)
                    return 6
    else:
        for c, f in tasks:
            if cfg.verbose:
                print(f"[info] processing chapter {c}")
            try:
                res = process_one(c, f, cfg)
                if cfg.verbose:
                    print(f"Processed: {res}")
            except ExtractionNotImplementedError as e:
                print(f"[TODO] {e}")
                return 5
            except Exception as e:
                print(f"[error] {e}", file=sys.stderr)
                return 6

    if cfg.verbose:
        print("Done")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
