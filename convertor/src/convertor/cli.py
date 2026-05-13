"""Simple CLI: iterate volume directories under a root and generate kepub.epub files.

Usage: python -m convertor <root_dir> [--force-regen] [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from convertor.exit_codes import CLI_ERROR, SUCCESS
from convertor.kcc_adapter import KCCSettings, convert_volume
from packer.cli import setup_logging

logger = logging.getLogger("convertor")


def find_volume_dirs(root: Path) -> list[Path]:
    """Return immediate subdirectories of `root` that look like volume dirs.

    For now we consider every directory directly under `root` as a candidate volume directory.
    More advanced heuristics (match `vNN` suffix) can be added later.
    """
    return [p for p in sorted(root.iterdir()) if p.is_dir()]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convert volume directories under a root to kepub.epub using KCC"
    )
    p.add_argument("root", help="root folder containing volume directories")
    p.add_argument(
        "--force-regen",
        action="store_true",
        help="regenerate output files even if they already exist",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="don't actually run conversion; just print what would be done",
    )
    p.add_argument("--verbose", action="store_true", help="verbose logging")
    p.add_argument(
        "--loglevel",
        "-l",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "WARN"],
        help="explicit log level (overrides --verbose)",
    )
    p.add_argument(
        "--nb-worker", "-w", type=int, default=1, help="number of workers (default 1)"
    )

    kcc = p.add_argument_group("KCC settings")
    kcc.add_argument(
        "--profile",
        default="KoLC",
        help="KCC device profile (default: KoLC = Kobo Libra Colour)",
    )
    kcc.add_argument(
        "--manga-style",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="manga reading direction, right-to-left (default: on)",
    )
    kcc.add_argument(
        "--hq",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="high-quality mode (default: on)",
    )
    kcc.add_argument(
        "--forcecolor",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="force colour output (default: on)",
    )
    kcc.add_argument(
        "--rotation",
        type=int,
        default=2,
        choices=[0, 1, 2, 3],
        help="page rotation mode: 0=none, 1=90CW, 2=90CCW, 3=180 (default: 2)",
    )
    kcc.add_argument(
        "--cropping",
        type=int,
        default=2,
        choices=[0, 1, 2],
        help="cropping mode: 0=off, 1=safe, 2=aggressive (default: 2)",
    )
    return p


def _build_settings(args: argparse.Namespace) -> KCCSettings:
    return KCCSettings(
        profile=args.profile,
        hq=args.hq,
        rotation=args.rotation,
        manga_style=args.manga_style,
        forcecolor=args.forcecolor,
        cropping=args.cropping,
    )


def _process_volumes(
    vols: list[Path],
    settings: KCCSettings,
    *,
    force_regen: bool,
    dry_run: bool,
) -> int:
    for vol in vols:
        out_path = vol.parent / (vol.name + ".kepub.epub")

        if out_path.exists():
            if force_regen:
                try:
                    out_path.unlink()
                except OSError:
                    logger.warning("could not remove existing output: %s", out_path)
            else:
                logger.info("skipping existing output: %s", out_path)
                continue

        logger.info("%s -> %s", vol, out_path)

        try:
            convert_volume(vol, out_path, dry_run=dry_run, settings=settings)
            logger.info("generated: %s", out_path)
        except (RuntimeError, subprocess.CalledProcessError, OSError) as e:
            logger.error("conversion failed for %s: %s", vol, e)

    return SUCCESS


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    setup_logging(args.verbose, loglevel=args.loglevel)

    root = Path(args.root)
    if not root.exists():
        logger.error("root path does not exist: %s", root)
        return CLI_ERROR

    vols = find_volume_dirs(root)
    if not vols:
        logger.warning("no volume directories found under %s", root)
        return SUCCESS

    return _process_volumes(
        vols,
        _build_settings(args),
        force_regen=args.force_regen,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
