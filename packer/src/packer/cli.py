"""CLI layer: argument parsing, config building, and top-level orchestration."""
from __future__ import annotations

import argparse
import logging
import re
from typing import List, Optional

from .core import (
    find_cbz_files,
    parse_range,
)
from .worker import process_volume

logger = logging.getLogger(__name__)


class Config:
    def __init__(
        self,
        path: str,
        dest: str,
        serie: str,
        volume: int,
        chapter_range: List[int],
        nb_worker: int = 1,
        dry_run: bool = False,
        verbose: bool = False,
        force: bool = False,
        chapter_pat: Optional[re.Pattern] = None,
        extra_pat: Optional[re.Pattern] = None,
    ):
        self.path = path
        self.dest = dest
        self.serie = serie
        self.volume = volume
        self.chapter_range = chapter_range
        self.nb_worker = nb_worker
        self.dry_run = dry_run
        self.verbose = verbose
        self.force = force
        self._chapter_pat = chapter_pat
        self._extra_pat = extra_pat

    # convenience helper for worker module
    def has_comicinfo(self, path: str) -> bool:
        from .core import has_comicinfo

        return has_comicinfo(path)


def setup_logging(verbose: bool = False, loglevel: Optional[str] = None, force_color: Optional[bool] = None):
    """Configure root logger with a compact, colored formatter and emoji prefixes.

    - verbose -> DEBUG level, otherwise INFO
    - loglevel: explicit string level to override verbose (e.g. DEBUG|INFO|WARNING|ERROR)
    - force_color: True/False to override automatic TTY detection
    """
    root = logging.getLogger()
    root.handlers.clear()

    # Determine numeric level (loglevel overrides verbose)
    if loglevel:
        lvl = loglevel.upper()
        if lvl == 'WARN':
            lvl = 'WARNING'
        level = getattr(logging, lvl, logging.INFO)
    else:
        level = logging.DEBUG if verbose else logging.INFO

    handler = logging.StreamHandler()

    # Decide whether to use color based on the handler stream TTY or caller override
    stream = handler.stream
    if force_color is True:
        use_color = True
    elif force_color is False:
        use_color = False
    else:
        use_color = hasattr(stream, "isatty") and stream.isatty()

    class ColorFormatter(logging.Formatter):
        COLORS = {
            'DEBUG': '\x1b[34m',    # blue
            'INFO': '\x1b[32m',     # green
            'WARNING': '\x1b[33m',  # yellow
            'ERROR': '\x1b[31m',    # red
            'CRITICAL': '\x1b[31;1m',
        }
        EMOJI = {
            'DEBUG': '🔧',
            'INFO': '✅',
            'WARNING': '⚠️',
            'ERROR': '❌',
            'CRITICAL': '💥',
        }
        RESET = '\x1b[0m'

        def __init__(self, use_color: bool = True):
            super().__init__()
            self.use_color = use_color

        def format(self, record: logging.LogRecord) -> str:
            level = record.levelname
            emoji = self.EMOJI.get(level, '')
            if self.use_color:
                color = self.COLORS.get(level, '')
                prefix = f"{color}{emoji} {level}:{self.RESET}"
            else:
                prefix = f"{emoji} {level}:"
            # Base message
            msg = record.getMessage()
            # Simple formatting: prefix + message
            formatted = f"{prefix} {msg}"
            # Handle exception formatting if present
            if record.exc_info:
                formatted = f"{formatted}\n{self.formatException(record.exc_info)}"
            return formatted

    handler.setFormatter(ColorFormatter(use_color))
    root.setLevel(level)
    root.addHandler(handler)


def parse_batch_spec(batch: str):
    specs = [s for s in batch.split('-') if s.strip()]
    parsed = []
    for s in specs:
        m = re.match(r'(?i)v\s*0*([0-9]+):(.+)', s.strip())
        if not m:
            raise ValueError(f"invalid batch spec: {s}")
        vol_num = int(m.group(1))
        ranges = parse_range(m.group(2))
        parsed.append((vol_num, ranges))
    return parsed


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Pack .cbz chapters into volume directories")
    p.add_argument('--path', required=True, help='path to root directory containing .cbz files')
    p.add_argument('--dest', default=None, help='destination root (defaults to --path)')
    p.add_argument('--serie', required=True, help='series name used to name the volume directory')
    p.add_argument('--volume', type=int, help='volume number to create')
    p.add_argument('--chapter-range', help='chapter range, e.g. "1..12" or "1,3,5..8"')
    p.add_argument('--nb-worker', type=int, default=1, help='number of workers (default 1)')
    p.add_argument('--dry-run', action='store_true', help='simulate actions')
    p.add_argument('--verbose', action='store_true', help='verbose logging')
    p.add_argument('--force', action='store_true', help='overwrite chapter dirs if exist')

    p.add_argument('--pattern', choices=['default', 'mashle', 'fma'], default='default',
                   help='named filename pattern (e.g., "mashle" expects "Ch.013" / "Ch.013.5"; "fma" supports "Chap 13" and extras "Chap 13.5")')
    p.add_argument('--chapter-regex', type=str, default=None,
                   help='custom regex for matching main chapters (must capture base number as group 1)')
    p.add_argument('--extra-regex', type=str, default=None,
                   help='custom regex for matching extra chapters (must capture base number group1 and extra suffix group2)')

    p.add_argument('--batch', type=str, default=None,
                   help='batch volumes spec: "v01:1..3-v02:4..6" (multiple specs separated by "-")')
    p.add_argument('--loglevel', type=str, default=None,
                   choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'WARN'],
                   help='explicit log level (overrides --verbose)')

    args = p.parse_args(argv)

    setup_logging(args.verbose, loglevel=args.loglevel)

    dest = args.dest if args.dest else args.path

    # Validate args
    if args.batch and (args.volume or args.chapter_range):
        logger.error('--batch cannot be combined with --volume/--chapter-range')
        return 2
    if not args.batch and (args.volume is None or args.chapter_range is None):
        logger.error('either --batch or both --volume and --chapter-range must be provided')
        return 2

    # compile patterns
    chapter_pat = None
    extra_pat = None
    try:
        if args.chapter_regex:
            chapter_pat = re.compile(args.chapter_regex)
        if args.extra_regex:
            extra_pat = re.compile(args.extra_regex)
        if args.pattern == 'mashle' and not (chapter_pat or extra_pat):
            chapter_pat = re.compile(r'(?i)ch(?:\.|apter)?[\s._-]*0*([0-9]+)')
            extra_pat = re.compile(r'(?i)ch(?:\.|apter)?[\s._-]*0*([0-9]+)\.([0-9]+)')
        if args.pattern == 'fma' and not (chapter_pat or extra_pat):
            # FMA uses "Chap" and sometimes extras like Chap 16.1
            chapter_pat = re.compile(r'(?i)chap(?:\.|ter)?[\s._-]*0*([0-9]+)')
            extra_pat = re.compile(r'(?i)chap(?:\.|ter)?[\s._-]*0*([0-9]+)\.([0-9]+)')
    except re.error as e:
        logger.error(f'Invalid regex: {e}')
        return 2

    cbz_files = find_cbz_files(args.path)

    cfg = Config(
        path=args.path,
        dest=dest,
        serie=args.serie,
        volume=args.volume if args.volume else 0,
        chapter_range=parse_range(args.chapter_range) if args.chapter_range else [],
        nb_worker=args.nb_worker,
        dry_run=args.dry_run,
        verbose=args.verbose,
        force=args.force,
        chapter_pat=chapter_pat,
        extra_pat=extra_pat,
    )

    # Parse batch specs
    batch_specs = []
    if args.batch:
        try:
            batch_specs = parse_batch_spec(args.batch)
        except Exception as e:
            logger.error(e)
            return 2
    else:
        batch_specs = [(cfg.volume, cfg.chapter_range)]

    available_files = cbz_files.copy()
    for vol_num, ranges in batch_specs:
        cfg.volume = vol_num
        cfg.chapter_range = ranges
        rc, available_files = process_volume(vol_num, ranges, available_files, cfg)
        if rc != 0:
            return rc

    logger.info('Done')
    return 0
