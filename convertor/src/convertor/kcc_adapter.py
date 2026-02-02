"""Adapter for Kindle Comic Converter (KCC).

This module exposes a small, testable class that builds the argv list expected
by KCC and runs the `kcc` module via `runpy.run_module`. Per project policy we
execute KCC as a module (no subprocess fallback) to keep behavior consistent.

Design decisions:
- Use a `NamedTuple` for the built invocation to avoid anonymous tuples.
- Keep arguments passed to the module stable and matching the UI choices
  (manga, stretch/upscale, color, cropping, Kobo profile).
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, Tuple
import runpy
import sys
import logging

logger = logging.getLogger(__name__)


class KCCInvocation(NamedTuple):
    """Representation of a KCC module invocation.

    Attributes:
        args: tuple of command-line arguments passed to `sys.argv` for the module.
    """

    args: Tuple[str, ...]


class KCCAdapter:
    """Builds arguments and runs the KCC module.

    This class is intentionally small to make it easy to unit-test and mock.
    """

    MODULE_NAME = "kcc"

    def build_invocation(self, input_dir: Path, out_path: Path) -> KCCInvocation:
        """Build a `KCCInvocation` representing the argv to pass to the module.

        The returned invocation is a NamedTuple (no anonymous tuples used).
        """
        args: list[str] = []
        args.extend(["-o", str(out_path)])
        args.extend(["--profile", "kobo_libra_colour"])  # device/profile preference
        args.append("--hq")
        args.extend(["-r", "2"])  # double-page parsing mode
        args.append("--manga-style")
        args.append("--stretch")
        args.append("--forcecolor")
        args.extend(["--cropping", "2"])  # cropping mode
        args.append(str(input_dir))

        return KCCInvocation(tuple(args))

    def run_module(self, invocation: KCCInvocation) -> int:
        """Run the KCC module with the given invocation.

        Returns 0 on success; raises `RuntimeError` for non-zero exit codes.
        """
        prev_argv = sys.argv[:]
        try:
            sys.argv = [self.MODULE_NAME] + list(invocation.args)
            # runpy.run_module may raise SystemExit; capture it
            try:
                runpy.run_module(self.MODULE_NAME, run_name="__main__")
                return 0
            except SystemExit as se:
                code = int(se.code or 0)
                if code == 0:
                    return 0
                raise RuntimeError(f"kcc module exited with code {code}")
        finally:
            sys.argv = prev_argv


def convert_volume(volume_dir: Path, out_path: Path, dry_run: bool = False) -> Path:
    """Convert a volume folder into an EPUB/Kepub using KCC (module-only).

    This function uses :class:`KCCAdapter` internally. The public API purposely
    does not accept an `options` parameter — arguments passed to KCC are fixed
    to match the UI defaults.
    """
    adapter = KCCAdapter()
    invocation = adapter.build_invocation(volume_dir, out_path)

    cmd_display = " ".join([KCCAdapter.MODULE_NAME] + list(invocation.args))
    logger.debug("KCC invocation: %s", cmd_display)

    if dry_run:
        logger.info("Dry run: would execute %s", cmd_display)
        return out_path

    rc = adapter.run_module(invocation)
    if rc != 0:
        raise RuntimeError(f"kcc module returned non-zero exit code {rc}")
    return out_path
