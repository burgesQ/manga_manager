"""Simple CLI: iterate volume directories under a root and generate kepub.epub files.

Usage: python -m convertor <root_dir> [--force-regen] [--dry-run]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import logging
import sys

from .kcc_adapter import convert_volume

print(type(convert_volume))  # Devrait afficher <class 'module'> au lieu de <class 'function'>

logger = logging.getLogger('convertor')


def find_volume_dirs(root: Path) -> list[Path]:
    """Return immediate subdirectories of `root` that look like volume dirs.

    For now we consider every directory directly under `root` as a candidate volume directory.
    More advanced heuristics (match `vNN` suffix) can be added later.
    """
    return [p for p in sorted(root.iterdir()) if p.is_dir()]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Convert volume directories under a root to kepub.epub using KCC')
    p.add_argument('root', help='root folder containing volume directories')
    p.add_argument('--force-regen', action='store_true', help='regenerate output files even if they already exist')
    p.add_argument('--dry-run', action='store_true', help="don't actually run conversion; just print what would be done")
    p.add_argument('--verbose', action='store_true', help='verbose logging')

    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(levelname)s: %(message)s')

    root = Path(args.root)
    if not root.exists():
        logger.error('root path does not exist: %s', root)
        return 2

    vols = find_volume_dirs(root)
    if not vols:
        logger.warning('no volume directories found under %s', root)
        return 0

    for vol in vols:
        # TODO: find better naming convention that feet calibre meta auto-discovery.
        # Need to find the appropriate doc about it.
        # Otherwise, will probably need to inject some cbz meta info (not loaded by epub AFAIR ?)
        out_path = vol.with_suffix(vol.suffix + '.kepub.epub')
        if out_path.exists() and not args.force_regen:
            logger.info('skipping existing output: %s', out_path)
            continue
        logger.info('%s -> %s', vol, out_path)
        # if args.dry_run:
        #     continue
        try:
            convert_volume(
                vol,
                out_path,
                options={
                    'manga_mode': True,
                    'stretch': True,
                    'color': True,
                    'crop': True,
                },
                dry_run=args.dry_run)
            logger.info('generated: %s', out_path)
        except Exception as e:
            logger.error('conversion failed for %s: %s', vol, e)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
