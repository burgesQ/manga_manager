"""Convertor package: thin wrapper around Kindle Comic Converter (KCC).

Public API:
- convert_volume(volume_dir: Path, out_path: Optional[Path]=None, *, options: dict=None)

This package prefers invoking KCC as an importable module (runpy.run_module) and falls back
to invoking the `kcc` CLI via subprocess when import-based execution is not available.
"""
from __future__ import annotations

import sys
from pathlib import Path
# When executed as a script the package may not be importable using relative
# imports. Ensure the package `src` directory is on sys.path so absolute
# imports like `import packer.core` work when running this file directly.
_pkg_src = str(Path(__file__).resolve().parent.parent)
if _pkg_src not in sys.path:
    sys.path.insert(0, _pkg_src)

from convertor.cli import main

#
# from .kcc_adapter import convert_volume as _convert_volume

# """Simple CLI: iterate volume directories under a root and generate kepub.epub files.

# Usage: python -m convertor <root_dir> [--force-regen] [--dry-run]
# """


# import argparse
# from pathlib import Path
# import logging
# import sys


# logger = logging.getLogger('convertor')


# def convert_volume(volume_dir: Path, out_path: Path | None = None, *, options: dict | None = None):
#     """Convert a volume directory into a kepub.epub file using KCC.

#     Args:
#         volume_dir: path to the folder holding the volume images (and possibly `.cbz` already extracted files).
#         out_path: destination path for the generated `.kepub.epub`. If omitted, defaults to ``volume_dir.with_suffix('.kepub.epub')``.
#         options: adapter options passed to KCC (boolean flags like ``manga_mode``, ``stretch``, ``color``, ``crop``).

#     Returns the path to the generated file on success.
#     Raises subprocess.CalledProcessError or RuntimeError on failure.
#     """
#     volume_dir = Path(volume_dir)
#     if out_path is None:
#         out_path = volume_dir.with_suffix(volume_dir.suffix + '.kepub.epub')
#     return _convert_volume(volume_dir, Path(out_path), options or {})

# def find_volume_dirs(root: Path) -> list[Path]:
#     """Return immediate subdirectories of `root` that look like volume dirs.

#     For now we consider every directory directly under `root` as a candidate volume directory.
#     More advanced heuristics (match `vNN` suffix) can be added later.
#     """
#     return [p for p in sorted(root.iterdir()) if p.is_dir()]


# def main(argv=None) -> int:
#     p = argparse.ArgumentParser(description='Convert volume directories under a root to kepub.epub using KCC')
#     p.add_argument('root', help='root folder containing volume directories')
#     p.add_argument('--force-regen', action='store_true', help='regenerate output files even if they already exist')
#     p.add_argument('--dry-run', action='store_true', help="don't actually run conversion; just print what would be done")
#     p.add_argument('--verbose', action='store_true', help='verbose logging')

#     args = p.parse_args(argv)

#     logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(levelname)s: %(message)s')

#     root = Path(args.root)
#     if not root.exists():
#         logger.error('root path does not exist: %s', root)
#         return 2

#     vols = find_volume_dirs(root)
#     if not vols:
#         logger.warning('no volume directories found under %s', root)
#         return 0

#     for vol in vols:
#         out_path = vol.with_suffix(vol.suffix + '.kepub.epub')
#         if out_path.exists() and not args.force_regen:
#             logger.info('skipping existing output: %s', out_path)
#             continue
#         logger.info('%s -> %s', vol, out_path)
#         if args.dry_run:
#             continue
#         try:
#             convert_volume(vol, out_path, options={
#                 'manga_mode': True,
#                 'stretch': True,
#                 'color': True,
#                 'crop': True,
#             })
#             logger.info('generated: %s', out_path)
#         except Exception as e:
#             logger.error('conversion failed for %s: %s', vol, e)
#     return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
