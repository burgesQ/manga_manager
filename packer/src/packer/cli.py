"""CLI layer: argument parsing, config building, and top-level orchestration."""

from __future__ import annotations

import argparse
import logging
import os
import re
import time
from typing import Optional

from .config import Config
from .core import (
    NAMED_PATTERNS,
    find_cbz_files,
    parse_range,
)
from .exit_codes import CLI_ERROR, SUCCESS
from .types_ import CoverMapping
from .worker import process_volume

logger = logging.getLogger(__name__)


class _CLIError(Exception):
    """Raised after logging a CLI-level error so main() can return CLI_ERROR."""


def setup_logging(
    verbose: bool = False,
    loglevel: Optional[str] = None,
    force_color: Optional[bool] = None,
):
    """Configure root logger with a compact, coloured formatter and emoji.

    - verbose -> DEBUG level, otherwise INFO
    - loglevel: explicit string level to override verbose
      (e.g. DEBUG|INFO|WARNING|ERROR)
    - force_color: True/False to override automatic TTY detection
    """
    root = logging.getLogger()
    root.handlers.clear()

    # Determine numeric level (loglevel overrides verbose)
    if loglevel:
        lvl = loglevel.upper()
        if lvl == "WARN":
            lvl = "WARNING"
        level = getattr(logging, lvl, logging.INFO)
    else:
        level = logging.DEBUG if verbose else logging.INFO

    handler = logging.StreamHandler()

    # Decide whether to use colour based on the handler stream TTY or caller override
    stream = handler.stream
    if force_color is True:
        use_color = True
    elif force_color is False:
        use_color = False
    else:
        use_color = hasattr(stream, "isatty") and stream.isatty()

    class ColorFormatter(logging.Formatter):
        COLORS = {
            "DEBUG": "\x1b[34m",  # blue
            "INFO": "\x1b[32m",  # green
            "WARNING": "\x1b[33m",  # yellow
            "ERROR": "\x1b[31m",  # red
            "CRITICAL": "\x1b[31;1m",
        }
        EMOJI = {
            "DEBUG": "🔧",
            "INFO": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "💥",
        }
        RESET = "\x1b[0m"

        def __init__(self, use_color: bool = True):
            super().__init__()
            self.use_color = use_color

        def format(self, record: logging.LogRecord) -> str:
            level = record.levelname
            emoji = self.EMOJI.get(level, "")
            if self.use_color:
                color = self.COLORS.get(level, "")
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


def parse_batch_spec(batch: str) -> list[tuple[int, list[int]]]:
    """Parse a batch spec string into a list of (volume, chapter_range) tuples.

    Format: `vNN:range-vMM:range`, e.g. `v01:1..3-v02:4..6`.

    Returns a list of tuples: [(1, [1,2,3]), (2, [4,5,6])].

    Example:
    >>> parse_batch_spec('v01:1..3-v02:4..6')
    [(1, [1, 2, 3]), (2, [4, 5, 6])]
    """
    specs = [s for s in batch.split("-") if s.strip()]
    parsed = []
    for s in specs:
        m = re.match(r"(?i)v\s*0*([0-9]+):(.+)", s.strip())
        if not m:
            raise ValueError(f"invalid batch spec: {s}")
        vol_num = int(m.group(1))
        ranges = parse_range(m.group(2))
        parsed.append((vol_num, ranges))
    return parsed


def parse_batch_file(file_path: str) -> list[tuple[int, list[int]]]:
    """Parse a simple batch file where each non-empty line is a CSV: "vol, chapters".

    Lines beginning with `#` or blank lines are ignored. Volume may be written
    as `v01` or `1`.

    Example file contents:
        v01,1..8
        2,9..17

    Returns:
        List[Tuple[int, List[int]]]
    """
    specs = []
    with open(file_path, "r", encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            parts = [p.strip() for p in ln.split(",") if p.strip()]
            if len(parts) < 2:
                raise ValueError(f"invalid batch file line: {ln}")
            vol_spec, range_spec = parts[0], parts[1]
            m = re.match(r"(?i)v?\s*0*([0-9]+)", vol_spec)
            if not m:
                raise ValueError(f"invalid volume spec in batch file: {vol_spec}")
            vol_num = int(m.group(1))
            ranges = parse_range(range_spec)
            specs.append((vol_num, ranges))
    return specs


def load_config_from_path(path: str):
    """Load an optional JSON config file (`packer.json`) from `path`.

    Supported keys (optional): `pattern`, `chapter_regex`, `extra_regex`,
    `nb_worker`, `batch_file`.

    Raises:
        ValueError: if a `packer.json` file is present but cannot be parsed as
                    a valid JSON object (dict). The caller should treat this as
                    a configuration error and abort.

    Returns an empty dict when no config file is present.
    """
    import json

    cfg_path = os.path.join(path, "packer.json")
    if not os.path.exists(cfg_path):
        return {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError(
                    f"Invalid packer.json ({cfg_path}): "
                    "top-level JSON must be an object"
                )
            return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid packer.json ({cfg_path}): {e.msg}")
    except Exception as e:
        raise ValueError(f"Invalid packer.json ({cfg_path}): {e}")


# ---------------------------------------------------------------------------
# Private helpers extracted from main()
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Pack .cbz chapters into volume directories"
    )
    p.add_argument(
        "--path", required=True, help="path to root directory containing .cbz files"
    )
    p.add_argument("--dest", default=None, help="destination root (defaults to --path)")
    p.add_argument(
        "--serie",
        required=False,
        default=None,
        help="series name used to name the volume directory "
        "(can be provided via packer.json)",
    )
    p.add_argument("--volume", type=int, help="volume number to create")
    p.add_argument("--chapter-range", help='chapter range, e.g. "1..12" or "1,3,5..8"')
    p.add_argument(
        "--nb-worker", type=int, default=1, help="number of workers (default 1)"
    )
    p.add_argument("--dry-run", action="store_true", help="simulate actions")
    p.add_argument("--verbose", action="store_true", help="verbose logging")
    p.add_argument(
        "--force", action="store_true", help="overwrite chapter dirs if exist"
    )
    p.add_argument(
        "--pattern",
        choices=["default", "mangadex", "mangafire", "animeSama"],
        default="default",
        help='named pattern: "mangadex" expects "Ch.013" / "Ch.013.5" (MangaDex/Tachiyomi); '
        '"mangafire" expects "Chap 13" / "Chap 13.5" (MangaFire); '
        '"animeSama" expects "Chapitre 13" (French; animesama.fr)',
    )
    p.add_argument(
        "--chapter-regex",
        type=str,
        default=None,
        help="custom regex for matching main chapters "
        "(must capture base number as group 1)",
    )
    p.add_argument(
        "--extra-regex",
        type=str,
        default=None,
        help="custom regex for matching extra chapters "
        "(must capture base number group1 and extra suffix group2)",
    )
    p.add_argument(
        "--batch",
        type=str,
        default=None,
        help='batch volumes spec: "v01:1..3-v02:4..6" '
        '(multiple specs separated by "-")',
    )
    p.add_argument(
        "--batch-file",
        type=str,
        default=None,
        help='path to a batch file (CSV lines: "vol, chapters" e.g. "v01,1..8")',
    )
    p.add_argument(
        "--loglevel",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "WARN"],
        help="explicit log level (overrides --verbose)",
    )
    return p


def _apply_path_config(args: argparse.Namespace) -> list[CoverMapping] | None:
    """Load packer.json from args.path, merge defaults into args, return covers.

    Mutates args in place. Raises _CLIError on invalid packer.json.
    """
    try:
        path_config = load_config_from_path(args.path)
    except ValueError as e:
        logger.error(str(e))
        raise _CLIError from e

    if path_config:
        if args.pattern == "default" and "pattern" in path_config:
            args.pattern = path_config["pattern"]
        if args.chapter_regex is None and "chapter_regex" in path_config:
            args.chapter_regex = path_config["chapter_regex"]
        if args.extra_regex is None and "extra_regex" in path_config:
            args.extra_regex = path_config["extra_regex"]
        if args.nb_worker == 1 and "nb_worker" in path_config:
            args.nb_worker = int(path_config["nb_worker"])
        if args.batch_file is None and "batch_file" in path_config:
            args.batch_file = (
                os.path.join(args.path, path_config["batch_file"])
                if not os.path.isabs(path_config["batch_file"])
                else path_config["batch_file"]
            )
        if args.serie is None and "serie" in path_config:
            args.serie = path_config["serie"]

    covers: list[CoverMapping] | None = None
    if path_config and "covers" in path_config:
        covers_dict = path_config["covers"]
        if not isinstance(covers_dict, dict):
            logger.warning("covers in packer.json must be a dict, skipping")
        else:
            try:
                covers = [
                    CoverMapping(volume=int(vol), cover_path=path)
                    for vol, path in covers_dict.items()
                ]
                logger.debug(f"loaded {len(covers)} cover mapping(s) from packer.json")
            except (ValueError, TypeError) as e:
                logger.warning(f"invalid covers config in packer.json: {e}, skipping")

    if covers:
        for cm in covers:
            if not os.path.exists(cm.cover_path):
                logger.warning(
                    f"cover declared for volume {cm.volume} not found: {cm.cover_path}"
                )

    return covers


def _validate_args(args: argparse.Namespace) -> None:
    """Validate parsed args. Raises _CLIError on invalid combinations.

    May mutate args.batch_file when a .batch file is auto-discovered.
    """
    if args.batch and (args.volume or args.chapter_range):
        logger.error("--batch cannot be combined with --volume/--chapter-range")
        raise _CLIError

    if not (args.batch or args.batch_file) and (
        args.volume is None or args.chapter_range is None
    ):
        discovered_batch = os.path.join(args.path, ".batch")
        if os.path.exists(discovered_batch):
            args.batch_file = discovered_batch
        else:
            logger.error(
                "either --batch or both --volume and --chapter-range must be provided"
            )
            raise _CLIError

    if args.serie is None:
        logger.error("either --serie or a `serie` key in packer.json must be provided")
        raise _CLIError


def _compile_patterns(
    args: argparse.Namespace,
) -> tuple[Optional[re.Pattern], Optional[re.Pattern]]:
    """Compile regex patterns from args. Raises _CLIError on invalid regex."""
    chapter_pat = None
    extra_pat = None
    try:
        if args.chapter_regex:
            chapter_pat = re.compile(args.chapter_regex)
        if args.extra_regex:
            extra_pat = re.compile(args.extra_regex)
        if args.pattern in NAMED_PATTERNS and not (chapter_pat or extra_pat):
            chapter_pat, extra_pat = NAMED_PATTERNS[args.pattern]
            logger.debug(f"using named regex pattern: {args.pattern}")
    except re.error as e:
        logger.error(f"Invalid regex: {e}")
        raise _CLIError from e
    return chapter_pat, extra_pat


def _resolve_batch_specs(
    args: argparse.Namespace, cfg: Config
) -> list[tuple[int, list[int]]]:
    """Resolve batch specs from args. Raises _CLIError on parse failure."""
    if args.batch:
        try:
            return parse_batch_spec(args.batch)
        except Exception as e:
            logger.error(e)
            raise _CLIError from e
    if args.batch_file:
        try:
            return parse_batch_file(args.batch_file)
        except Exception as e:
            logger.error(e)
            raise _CLIError from e
    return [(cfg.volume, cfg.chapter_range)]


def _run_batch(batch_specs: list[tuple[int, list[int]]], cfg: Config) -> int:
    """Execute all batch volumes and return the exit code."""
    cbz_files = find_cbz_files(cfg.path)
    total_volumes = len(batch_specs)
    total_chapters = sum(len(ranges) for _, ranges in batch_specs)
    start_time = time.monotonic()
    dry_prefix = "[DRY RUN] " if cfg.dry_run else ""
    logger.info(
        f"{dry_prefix}📦 Processing {total_chapters} chapters → {total_volumes} volume(s)"
    )

    available_files = cbz_files.copy()
    for vol_num, ranges in batch_specs:
        cfg.volume = vol_num
        cfg.chapter_range = ranges
        rc, available_files = process_volume(vol_num, ranges, available_files, cfg)
        if rc != 0:
            return rc

    elapsed = time.monotonic() - start_time
    logger.info(
        f"✅ Done — {total_chapters} chapters in {total_volumes} volume(s) ({elapsed:.1f}s)"
    )
    return SUCCESS


def main(argv=None) -> int:
    """Command-line entry point for the `packer` tool."""
    args = _build_parser().parse_args(argv)
    setup_logging(args.verbose, loglevel=args.loglevel)
    dest = args.dest if args.dest else args.path

    try:
        covers = _apply_path_config(args)
        _validate_args(args)
        chapter_pat, extra_pat = _compile_patterns(args)
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
            covers=covers,
        )
        batch_specs = _resolve_batch_specs(args, cfg)
    except _CLIError:
        return CLI_ERROR

    return _run_batch(batch_specs, cfg)
