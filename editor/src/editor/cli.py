"""Simple CLI: iterate volume directories under a root and generate kepub.epub files.

Usage: python -m convertor <root_dir> [--force-regen] [--dry-run]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import logging
import sys


logger = logging.getLogger('convertor')

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Edit epub files metadata')
    # p.add_argument('root', help='root folder containing volume directories')
    # p.add_argument('--force-regen', action='store_true', help='regenerate output files even if they already exist')
    p.add_argument('--dry-run', action='store_true', help="don't actually run conversion; just print what would be done")
    p.add_argument('--verbose', action='store_true', help='verbose logging')

    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(levelname)s: %(message)s')

    # root = Path(args.root)
    # if not root.exists():
    #     logger.error('root path does not exist: %s', root)
    #     return 2

    # take a path to epub file ?
    # Or take a path to dir olding epub
    # If path to dir, need a "struct" file

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
