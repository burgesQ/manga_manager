"""EPUB Metadata Manager

Inject or dump metadata from EPUB files based on YAML configuration.

Usage:
    # Inject metadata into EPUBs
    python epub_metadata.py inject <epub_dir> <metadata.yaml> [--force] [--dry-run]

    # Dump existing metadata from EPUBs
    python epub_metadata.py dump <epub_dir> [--output metadata.yaml]

Examples:
    python epub_metadata.py inject ./volumes mashle.yaml
    python epub_metadata.py inject ./volumes mashle.yaml --force
    python epub_metadata.py dump ./volumes --output current_metadata.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from editor.editor_full import dump_metadata, inject_metadata
from packer.cli import setup_logging

logger = logging.getLogger("editor")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="EPUB files metadata manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    # parser.add_argument(
    #     "--loglevel",
    #     "-l",
    #     type=str,
    #     default=None,
    #     choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "WARN"],
    #     help="explicit log level (overrides --verbose)",
    # )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Inject command
    inject_parser = subparsers.add_parser("inject", help="Inject metadata into EPUBs")
    inject_parser.add_argument(
        "epub_dir", type=Path, help="Directory containing EPUB files"
    )
    inject_parser.add_argument("metadata", type=Path, help="YAML metadata file")
    inject_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing metadata"
    )
    inject_parser.add_argument(
        "--dry-run", action="store_true", help="Simulate without making changes"
    )
    inject_parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    inject_parser.add_argument(
        "--loglevel",
        "-l",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "WARN"],
        help="explicit log level (overrides --verbose)",
    )

    # Dump command
    dump_parser = subparsers.add_parser("dump", help="Dump metadata from EPUBs")
    dump_parser.add_argument(
        "epub_dir", type=Path, help="Directory containing EPUB files"
    )
    dump_parser.add_argument(
        "--output", "-o", type=Path, help="Output YAML file (default: print to stdout)"
    )
    dump_parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    dump_parser.add_argument(
        "--loglevel",
        "-l",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "WARN"],
        help="explicit log level (overrides --verbose)",
    )

    args = parser.parse_args(argv)

    print(f"{args}")

    if not args.command:
        parser.print_help()
        return 1

    setup_logging(args.verbose, loglevel=args.loglevel)

    # Execute command
    if args.command == "inject":
        print("inject")
        return inject_metadata(
            args.epub_dir,
            args.metadata,
            force=args.force,
            dry_run=args.dry_run,
        )
    elif args.command == "dump":
        print("dump")
        return dump_metadata(args.epub_dir, args.output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
