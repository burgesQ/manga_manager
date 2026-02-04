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

import logging
import runpy
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, NamedTuple, Tuple

logger = logging.getLogger(__name__)


class KCCInvocation(NamedTuple):
    """Representation of a KCC module invocation.

    Attributes:
        args: tuple of command-line arguments passed to `sys.argv` for the module.
    """

    args: List[str]


class KCCAdapter:
    """Builds arguments and runs the KCC module.

    This class is intentionally small to make it easy to unit-test and mock.
    """

    def build_invocation(self, input_dir: Path, out_path: Path) -> KCCInvocation:
        """Build a `KCCInvocation` representing the argv to pass to the module.

        The returned invocation is a NamedTuple (no anonymous tuples used).
        """
        args: list[str] = []
        args.extend(["-o", str(out_path)])
        args.extend(["--profile", "KoLC"])  # device/profile preference
        args.append("--hq")
        args.extend(["-r", "2"])  # double-page parsing mode
        args.append("--manga-style")
        args.append("--stretch")
        args.append("--forcecolor")
        args.extend(["--cropping", "2"])  # cropping mode
        args.append(str(input_dir))

        return KCCInvocation(args)

    def run_module(self, invocation: KCCInvocation, dry_run: bool = False) -> int:
        """Run the KCC module with the given invocation.

        Tries a list of candidate module names (see ``POSSIBLE_MODULE_NAMES``)
        and runs the first one that is importable. This keeps behavior module-only
        while being robust to packaging variations.

        Returns 0 on success; raises `RuntimeError` for non-zero exit codes or
        when no suitable module can be found.
        """
        prev_argv = sys.argv[:]

        # Use kcc-c2e which is the CLI command installed by kindlecomicconverter
        cmd = ["kcc-c2e"] + invocation.args
        logger.debug("Running kcc: %s", shlex.join(cmd))

        if dry_run:
            logger.info("Dry run - would execute: %s", shlex.join(cmd))

            return 0

        res = subprocess.run(cmd, capture_output=True, text=True)

        if res.stdout:
            logger.debug("kcc stdout: %s", res.stdout)
        if res.stderr:
            logger.debug("kcc stderr: %s", res.stderr)

        if res.returncode != 0:
            raise subprocess.CalledProcessError(
                res.returncode, cmd, res.stdout, res.stderr
            )

        return res.returncode


def convert_volume(volume_dir: Path, out_path: Path, dry_run: bool = False) -> Path:
    """Convert a volume folder into an EPUB/Kepub using KCC (module-only).

    This function uses :class:`KCCAdapter` internally. The public API purposely
    does not accept an `options` parameter — arguments passed to KCC are fixed
    to match the UI defaults.
    """
    adapter = KCCAdapter()
    args = adapter.build_invocation(volume_dir, out_path)

    # cmd_display = " ".join([KCCAdapter.MODULE_NAME] + list(invocation.args))
    logger.debug(f"kcc CLI args invocation: {args}")

    # if dry_run:
    #     logger.info("Dry run: would execute %s", cmd_display)
    #     return out_path

    rc = adapter.run_module(args, dry_run=dry_run)
    if rc != 0:
        raise RuntimeError(f"kcc module returned non-zero exit code {rc}")
    return out_path
