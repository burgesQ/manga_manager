"""Simple CLI: iterate volume directories under a root and generate kepub.epub files.

Usage: python -m convertor <root_dir> [--force-regen] [--dry-run]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import logging
import sys

from packer.cli import setup_logging

# from .worker import convert_volumes_parallel, print_summary
from .kcc_adapter import convert_volume

logger = logging.getLogger('convertor')


def find_volume_dirs(root: Path) -> list[Path]:
    """Return immediate subdirectories of `root` that look like volume dirs.

    For now we consider every directory directly under `root` as a candidate volume directory.
    More advanced heuristics (match `vNN` suffix) can be added later.
    """
    return [p for p in sorted(root.iterdir()) if p.is_dir()]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Convert volume directories under a root to kepub.epub using KCC')
    p.add_argument(
        'root',
        help='root folder containing volume directories')
    p.add_argument(
        '--force-regen',
        action='store_true',
        help='regenerate output files even if they already exist')
    p.add_argument(
        '--dry-run',
        action='store_true',
        help="don't actually run conversion; just print what would be done")
    p.add_argument(
        '--verbose',
        action='store_true',
        help='verbose logging')
    p.add_argument(
        '--loglevel', '-l',
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "WARN"],
        help='explicit log level (overrides --verbose)',
    )
    p.add_argument(
        '--nb-worker', '-w',
        type=int,
        default=1,
        help="number of workers (default 1)")

    args = p.parse_args(argv)

    setup_logging(args.verbose, loglevel=args.loglevel)

    root = Path(args.root)
    if not root.exists():
        logger.error('root path does not exist: %s', root)
        return 2

    vols = find_volume_dirs(root)
    if not vols:
        logger.warning('no volume directories found under %s', root)
        return 0

    # each vol can be assign to a worker.
    # Worker mode. KCC doesn't seems freendly with it ..
    # res= convert_volumes_parallel(
    #     vols,
    #     force_regen=args.force_regen,
    #     dry_run=args.dry_run,
    #     max_workers=args.nb_worker)
    # print_summary(res)

    for vol in vols:
        out_path = vol.with_suffix(vol.suffix + '.kepub.epub')


        if out_path.exists():
            if args.force_regen:
                # TODO: remove existing file before processing
                pass
            else:
                logger.info('skipping existing output: %s', out_path)
                continue

        logger.info('%s -> %s', vol, out_path)

        try:
            convert_volume(vol, out_path, dry_run=args.dry_run)
            logger.info('generated: %s', out_path)
        except Exception as e:
            logger.error('conversion failed for %s: %s', vol, e)

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
