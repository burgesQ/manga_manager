"""Simple CLI: iterate volume directories under a root and generate kepub.epub files.

Usage: python -m convertor <root_dir> [--preset {manga,comic}] [--force-regen]
       [--dry-run]

``--preset`` picks the base KCC settings (``manga`` = right-to-left, the
default; ``comic`` = left-to-right). Any explicit KCC flag overrides the preset.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

import shtab

from convertor.exit_codes import CLI_ERROR, SUCCESS
from convertor.kcc_adapter import (
    DEFAULT_PRESET,
    PRESETS,
    KCCSettings,
    convert_volume,
)
from packer.cli import add_version_arg, setup_logging

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

    kcc = p.add_argument_group(
        "KCC settings",
        "Unset flags take their value from --preset; explicit flags override it.",
    )
    kcc.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        default=DEFAULT_PRESET,
        help="base KCC settings: manga = right-to-left reading, comic = "
        "left-to-right reading; both keep colour on (default: manga)",
    )
    # Every flag below defaults to None so _build_settings can tell "not given"
    # apart from an explicit value and fall back to the preset.
    kcc.add_argument(
        "--profile",
        default=None,
        help="KCC device profile (preset default: KoLC = Kobo Libra Colour)",
    )
    kcc.add_argument(
        "--manga-style",
        default=None,
        action=argparse.BooleanOptionalAction,
        help="manga reading direction, right-to-left "
        "(preset default: on for manga, off for comic)",
    )
    kcc.add_argument(
        "--hq",
        default=None,
        action=argparse.BooleanOptionalAction,
        help="high-quality mode (preset default: on)",
    )
    kcc.add_argument(
        "--forcecolor",
        default=None,
        action=argparse.BooleanOptionalAction,
        help="force colour output (preset default: on)",
    )
    kcc.add_argument(
        "--rotation",
        type=int,
        default=None,
        choices=[0, 1, 2, 3],
        help="page rotation mode: 0=none, 1=90CW, 2=90CCW, 3=180 (preset default: 2)",
    )
    kcc.add_argument(
        "--cropping",
        type=int,
        default=None,
        choices=[0, 1, 2],
        help="cropping mode: 0=off, 1=safe, 2=aggressive (preset default: 2)",
    )
    kcc.add_argument(
        "--upscale",
        default=None,
        action=argparse.BooleanOptionalAction,
        help="upscale images smaller than device resolution (preset default: on)",
    )
    kcc.add_argument(
        "--blackborders",
        default=None,
        action=argparse.BooleanOptionalAction,
        help="fill remaining border bands with black instead of white "
        "(preset default: off)",
    )
    add_version_arg(p, "convertor")
    shtab.add_argument_to(p, "--print-completion")
    return p


def _build_settings(args: argparse.Namespace) -> KCCSettings:
    """Start from the ``--preset`` settings and apply every explicit KCC flag.

    A flag left unset on the command line is ``None`` and keeps the preset
    value; any other value (including ``False`` from ``--no-*``) overrides it.
    """
    preset = getattr(args, "preset", None) or DEFAULT_PRESET
    overrides = {
        field: value
        for field in KCCSettings._fields
        if (value := getattr(args, field, None)) is not None
    }
    settings = PRESETS[preset]._replace(**overrides)
    direction = "right-to-left" if settings.manga_style else "left-to-right"
    logger.info("Reading direction: %s (%s preset)", direction, preset)
    return settings


def _convert_one(
    vol: Path,
    settings: KCCSettings,
    *,
    force_regen: bool,
    dry_run: bool,
) -> bool:
    out_path = vol.parent / (vol.name + ".kepub.epub")

    if out_path.exists():
        if force_regen:
            try:
                out_path.unlink()
            except OSError:
                logger.warning("could not remove existing output: %s", out_path)
        else:
            logger.info("skipping existing output: %s", out_path)
            return True

    logger.info("%s -> %s", vol, out_path)

    try:
        convert_volume(vol, out_path, dry_run=dry_run, settings=settings)
        logger.info("generated: %s", out_path)
        return True
    except (RuntimeError, subprocess.CalledProcessError, OSError) as e:
        logger.error("conversion failed for %s: %s", vol, e)
        return False


def _process_volumes(
    vols: list[Path],
    settings: KCCSettings,
    *,
    force_regen: bool,
    dry_run: bool,
) -> int:
    ok = fail = 0
    for vol in vols:
        if _convert_one(vol, settings, force_regen=force_regen, dry_run=dry_run):
            ok += 1
        else:
            fail += 1
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info("Total volumes:  %d", len(vols))
    logger.info("Converted/skipped: %d", ok)
    logger.info("Failed:         %d", fail)
    logger.info("=" * 60)
    return CLI_ERROR if fail else SUCCESS


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
