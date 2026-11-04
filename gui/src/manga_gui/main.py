"""Entry point of ``manga-gui``: parse CLI options and start the NiceGUI server."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from nicegui import ui

from packer.cli import add_version_arg, setup_logging

from .exit_codes import CLI_ERROR, SUCCESS
from .store import Store

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
APP_TITLE = "manga-gui"


class _CLIError(Exception):
    """Raised after logging a CLI-level error so main() can return CLI_ERROR."""


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="manga-gui",
        description="Web UI to configure and run the packer → convertor → editor "
        "pipeline",
    )
    p.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"interface to bind (default: {DEFAULT_HOST}; use 0.0.0.0 in Docker)",
    )
    p.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"port to listen on (default: {DEFAULT_PORT})",
    )
    p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help="store projects and runs under PATH instead of the XDG directories "
        "(~/.config/manga_manager, ~/.local/state/manga_manager)",
    )
    p.add_argument("--verbose", action="store_true", help="verbose logging")
    p.add_argument(
        "--loglevel",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "WARN"],
        help="explicit log level (overrides --verbose)",
    )
    add_version_arg(p, "manga-gui")
    return p


def _validate_args(args: argparse.Namespace) -> None:
    if not 0 < args.port < 65536:
        logger.error("--port must be between 1 and 65535, got %s", args.port)
        raise _CLIError
    if args.data_dir is not None and args.data_dir.exists():
        if not args.data_dir.is_dir():
            logger.error("--data-dir is not a directory: %s", args.data_dir)
            raise _CLIError


def _register_pages(store: Store) -> None:
    """Register the NiceGUI pages (placeholder until the wizard pages land)."""

    @ui.page("/")
    def index() -> None:
        ui.label(APP_TITLE).classes("text-h4")
        projects = store.list_projects()
        ui.label(f"{len(projects)} project(s) in {store.projects_dir}")
        for project in projects:
            ui.label(f"{project.name} ({project.kind.value}) — {project.source}")


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point for the ``manga-gui`` tool."""
    args = _build_parser().parse_args(argv)
    setup_logging(args.verbose, loglevel=args.loglevel)
    try:
        _validate_args(args)
    except _CLIError:
        return CLI_ERROR

    store = Store(args.data_dir)
    logger.info("projects: %s — runs: %s", store.projects_dir, store.runs_dir)
    _register_pages(store)
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
