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


def extract_chapter_number(filename: str) -> List[int]:
    """Return list of chapter numbers found in `filename` (may be empty).

    Uses a set of regex patterns to be flexible with naming conventions.
    """
    base = os.path.basename(filename)
    nums: List[int] = []
    for pat in CHAPTER_PATTERNS:
        m = pat.search(base)
        if m:
            try:
                nums.append(int(m.group(1)))
            except Exception:
                continue
    return nums


def find_cbz_files(root: str) -> List[str]:
    files: List[str] = []
    for entry in os.listdir(root):
        if entry.lower().endswith('.cbz') and os.path.isfile(os.path.join(root, entry)):
            files.append(os.path.join(root, entry))
    return files


def map_chapters_to_files(cbz_files: Sequence[str]) -> Dict[int, List[str]]:
    """Map detected chapter numbers to list of files that match them."""
    mapping: Dict[int, List[str]] = {}
    for p in cbz_files:
        nums = extract_chapter_number(p)
        for n in nums:
            mapping.setdefault(n, []).append(p)
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


def process_one(chapter: int, src_file: str, cfg: Config) -> Tuple[int, str]:
    """Process one chapter: validate comicinfo, move file, create chapter dir.

    This function is suitable for running in a ProcessPoolExecutor.
    It will raise `ExtractionNotImplementedError` after creating the chapter dir
    to signal that extraction is intentionally not implemented yet.
    """
    if cfg.verbose:
        print(f"[worker] start chapter={chapter} file={src_file}")

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

    # Create chapter dir
    chapter_dir = os.path.join(volume_dir, f"Chapter {chapter:03d}")
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
            return chapter, dest_archive
    else:
        if cfg.verbose:
            print(f"[worker] creating chapter dir: {chapter_dir}")
        if not cfg.dry_run:
            os.makedirs(chapter_dir, exist_ok=True)
        elif cfg.verbose:
            print(f"[dry-run] mkdir {chapter_dir}")

    # Safe extraction (prevent path traversal)
    try:
        with zipfile.ZipFile(dest_archive, 'r') as z:
            names = z.namelist()
            for member in names:
                parts = PurePosixPath(member).parts
                if '..' in parts or member.startswith('/') or member.startswith('\\'):
                    raise RuntimeError(f"Unsafe path in archive: {member}")
            if cfg.dry_run:
                if cfg.verbose:
                    print(f"[dry-run] extract {dest_archive} -> {chapter_dir}")
            else:
                z.extractall(chapter_dir)
                if cfg.verbose:
                    print(f"[worker] extracted {dest_archive} -> {chapter_dir}")
    except zipfile.BadZipFile:
        raise RuntimeError(f"Bad zip file: {dest_archive}")

    return chapter, dest_archive


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

    # Validate presence & uniqueness
    if cfg.verbose:
        print(f"[info] validating requested chapters: {cfg.chapter_range}")
    for c in cfg.chapter_range:
        files = mapping.get(c, [])
        if not files:
            print(f"[error] missing chapter {c}", file=sys.stderr)
            return 3
        if len(files) > 1:
            print(f"[error] multiple archives match chapter {c}: {files}", file=sys.stderr)
            return 4

    # Prepare tasks
    tasks: List[Tuple[int, str]] = [(c, mapping[c][0]) for c in cfg.chapter_range]
    if cfg.verbose:
        print("[info] planned tasks:")
        for c, f in tasks:
            print(f"[info]  chapter {c} -> {f}")

    # Process (use ProcessPoolExecutor as requested)
    if cfg.nb_worker > 1:
        if cfg.verbose:
            print(f"[info] Using ProcessPoolExecutor with {cfg.nb_worker} workers")
        with concurrent.futures.ProcessPoolExecutor(max_workers=cfg.nb_worker) as ex:
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
def main():
    print("Hello from packer!")


if __name__ == "__main__":
    main()
