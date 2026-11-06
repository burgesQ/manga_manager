"""Entry point of ``manga-gui``.

- ``manga-gui [options]`` (no subcommand): start the NiceGUI server;
- ``manga-gui import [options]``: create project profiles from a metadata dir and
  a library root (:mod:`manga_gui.discovery`), logging the plan first.

``--library-root`` / ``--metadata-dir`` override the saved settings
(``<config>/settings.json``) for this session only.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from nicegui import ui

from packer.cli import add_version_arg, setup_logging

from .discovery import apply_import, format_plan, plan_import
from .exit_codes import CLI_ERROR, PROCESSING_ERROR, SUCCESS
from .models import Settings
from .pages import register_pages
from .store import Store

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
APP_TITLE = "manga-gui"


class _CLIError(Exception):
    """Raised after logging a CLI-level error so main() can return CLI_ERROR."""


def _user_path(text: str) -> Path:
    return Path(text).expanduser()


def _add_common_args(p: argparse.ArgumentParser, *, suppress: bool) -> None:
    """Options of both the server and ``import``.

    On the subparser the defaults are suppressed so that a value given before the
    subcommand (``manga-gui --data-dir X import``) is not reset.
    """

    def default(value: object) -> object:
        return argparse.SUPPRESS if suppress else value

    p.add_argument(
        "--data-dir",
        type=_user_path,
        default=default(None),
        metavar="PATH",
        help="store projects, runs and settings under PATH instead of the XDG "
        "directories (~/.config/manga_manager, ~/.local/state/manga_manager)",
    )
    p.add_argument(
        "--library-root",
        type=_user_path,
        default=default(None),
        metavar="PATH",
        help="library root holding the series folders (overrides the saved "
        "setting for this session)",
    )
    p.add_argument(
        "--metadata-dir",
        type=_user_path,
        default=default(None),
        metavar="PATH",
        help="folder of packer_<key>.json / <key>.yaml / chapters_<key>.yaml / "
        "vols_<key>.csv files (overrides the saved setting for this session)",
    )
    p.add_argument(
        "--verbose", action="store_true", default=default(False), help="verbose logging"
    )
    p.add_argument(
        "--loglevel",
        type=str,
        default=default(None),
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "WARN"],
        help="explicit log level (overrides --verbose)",
    )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="manga-gui",
        description="Web UI to configure and run the packer → convertor → editor "
        "pipeline. Without a subcommand, start the web server.",
    )
    p.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"interface to bind (default: {DEFAULT_HOST}, local only)",
    )
    p.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"port to listen on (default: {DEFAULT_PORT})",
    )
    _add_common_args(p, suppress=False)
    add_version_arg(p, "manga-gui")
    p.set_defaults(command=None)

    sub = p.add_subparsers(dest="command", metavar="COMMAND")
    imp = sub.add_parser(
        "import",
        help="create projects from a metadata dir and a library root",
        description="Match the files of the metadata dir (packer_<key>.json, "
        "<key>.yaml, chapters_<key>.yaml, vols_<key>.csv) to the series folders of "
        "the library root and create one project profile per series. Only profiles "
        "are written; existing projects are skipped unless --overwrite.",
    )
    _add_common_args(imp, suppress=True)
    imp.add_argument(
        "--dry-run", action="store_true", help="log the plan, write nothing"
    )
    imp.add_argument(
        "--overwrite", action="store_true", help="replace existing project profiles"
    )
    imp.add_argument(
        "--save-settings",
        action="store_true",
        help="also save --library-root / --metadata-dir as the default settings",
    )
    return p


def _check_dir(option: str, path: Path | None) -> None:
    if path is not None and not path.is_dir():
        logger.error("%s is not a directory: %s", option, path)
        raise _CLIError


def _validate_args(args: argparse.Namespace) -> None:
    if not 0 < args.port < 65536:
        logger.error("--port must be between 1 and 65535, got %s", args.port)
        raise _CLIError
    if args.data_dir is not None and args.data_dir.exists():
        _check_dir("--data-dir", args.data_dir)
    _check_dir("--library-root", args.library_root)
    _check_dir("--metadata-dir", args.metadata_dir)


def _make_store(args: argparse.Namespace) -> Store:
    overrides = Settings(library_root=args.library_root, metadata_dir=args.metadata_dir)
    return Store(args.data_dir, settings_overrides=overrides)


def _run_import(args: argparse.Namespace) -> int:
    store = _make_store(args)
    settings = store.effective_settings()
    if settings.library_root is None and settings.metadata_dir is None:
        logger.error(
            "nothing to import: give --library-root and / or --metadata-dir "
            "(or save them in the GUI)"
        )
        raise _CLIError
    _check_dir("library root", settings.library_root)
    _check_dir("metadata dir", settings.metadata_dir)
    logger.info(
        "library root: %s — metadata dir: %s — projects: %s",
        settings.library_root or "-",
        settings.metadata_dir or "-",
        store.projects_dir,
    )

    candidates = plan_import(settings.metadata_dir, settings.library_root, store)
    if not candidates:
        logger.warning("no series folder or metadata file found")
    for line in format_plan(candidates, overwrite=args.overwrite):
        logger.info(line)
    statuses = [c.status(overwrite=args.overwrite) for c in candidates]
    writes = statuses.count("new") + statuses.count("overwrite")
    if args.dry_run:
        logger.info("dry-run: %d project(s) would be written, nothing done", writes)
        return SUCCESS

    if args.save_settings:
        logger.info("saved settings to %s", store.save_settings(settings))
    report = apply_import(
        [c for c in candidates if c.importable], store, overwrite=args.overwrite
    )
    for slug, error in report.failed:
        logger.error("failed to import %s: %s", slug, error)
    logger.info("import: %s", report.summary())
    return PROCESSING_ERROR if report.failed else SUCCESS


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point for the ``manga-gui`` tool."""
    args = _build_parser().parse_args(argv)
    setup_logging(args.verbose, loglevel=args.loglevel)
    try:
        _validate_args(args)
        if args.command == "import":
            return _run_import(args)
    except _CLIError:
        return CLI_ERROR

    store = _make_store(args)
    logger.info("projects: %s — runs: %s", store.projects_dir, store.runs_dir)
    register_pages(store)
    ui.run(
        host=args.host,
        port=args.port,
        title=APP_TITLE,
        reload=False,
        show=False,
    )
    return SUCCESS


if __name__ in {"__main__", "__mp_main__"}:
    raise SystemExit(main(sys.argv[1:]))
