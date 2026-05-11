"""Adapter for Kindle Comic Converter (KCC).

This module exposes a small, testable class that builds the argv list expected
by KCC and runs the `kcc` module via `runpy.run_module`. Per project policy we
execute KCC as a module (no subprocess fallback) to keep behaviour consistent.

Design decisions:
- Use a `NamedTuple` for the built invocation to avoid anonymous tuples.
- Keep arguments passed to the module stable and matching the UI choices
  (manga, colour, cropping, Kobo profile).
"""

from __future__ import annotations

import logging
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import List, NamedTuple

logger = logging.getLogger(__name__)

COVER_FILENAME = "cover.webp"
COVER_CHAPTER_DIR = "Chapter 000"


def _inject_cover(volume_dir: Path, dry_run: bool) -> bool:
    """Copy cover.webp into Chapter 000/ so KCC treats it as the first page."""
    cover_src = volume_dir / COVER_FILENAME
    if not cover_src.exists():
        return False
    chapter_dir = volume_dir / COVER_CHAPTER_DIR
    if dry_run:
        logger.info(f"[DRY RUN] would create {chapter_dir} with cover")
        return True
    chapter_dir.mkdir(exist_ok=True)
    shutil.copy2(str(cover_src), str(chapter_dir / COVER_FILENAME))
    logger.info(f"📷 Cover injected: {chapter_dir / COVER_FILENAME}")
    return True


def _cleanup_cover_chapter(volume_dir: Path) -> None:
    """Remove the temporary Chapter 000/ dir created for cover injection."""
    chapter_dir = volume_dir / COVER_CHAPTER_DIR
    if chapter_dir.exists():
        shutil.rmtree(str(chapter_dir))
        logger.debug(f"Cleaned up temp cover dir: {chapter_dir}")


class KCCInvocation(NamedTuple):
    """Representation of a KCC module invocation.

    Attributes:
        args: tuple of command-line arguments passed to `sys.argv` for the module.
    """

    args: List[str]


class KCCSettings(NamedTuple):
    """KCC conversion settings.

    All defaults preserve the original hardcoded behaviour so existing callers
    that omit this argument are unaffected.
    """

    profile: str = "KoLC"
    hq: bool = True
    rotation: int = 2
    manga_style: bool = True
    forcecolor: bool = True
    cropping: int = 2


class KCCAdapter:
    """Builds arguments and runs the KCC module.

    This class is intentionally small to make it easy to unit-test and mock.
    """

    def build_invocation(
        self,
        input_dir: Path,
        out_path: Path,
        settings: KCCSettings = KCCSettings(),
    ) -> KCCInvocation:
        """Build a `KCCInvocation` representing the argv to pass to the module.

        The returned invocation is a NamedTuple (no anonymous tuples used).
        """
        args: list[str] = []
        args.extend(["-o", str(out_path)])
        args.extend(["--profile", settings.profile])
        if settings.hq:
            args.append("--hq")
        args.extend(["-r", str(settings.rotation)])
        if settings.manga_style:
            args.append("--manga-style")
        if settings.forcecolor:
            args.append("--forcecolor")
        args.extend(["--cropping", str(settings.cropping)])
        args.append(str(input_dir))

        return KCCInvocation(args)

    def run_module(self, invocation: KCCInvocation, dry_run: bool = False) -> int:
        """Run the KCC module with the given invocation.

        Tries a list of candidate module names (see ``POSSIBLE_MODULE_NAMES``)
        and runs the first one that is importable. This keeps behaviour module-only
        while being robust to packaging variations.

        Returns 0 on success; raises `RuntimeError` for non-zero exit codes or
        when no suitable module can be found.
        """
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


def convert_volume(
    volume_dir: Path,
    out_path: Path,
    dry_run: bool = False,
    settings: KCCSettings = KCCSettings(),
) -> Path:
    """Convert a volume folder into an EPUB/Kepub using KCC (module-only).

    This function uses :class:`KCCAdapter` internally. The public API purposely
    does not accept an `options` parameter — arguments passed to KCC are fixed
    to match the UI defaults.

    If a ``cover.webp`` file exists at the root of *volume_dir*, it is injected
    as ``Chapter 000/cover.webp`` before the KCC call so KCC renders it as the
    first page. The temporary directory is removed in the finally block.
    """
    adapter = KCCAdapter()
    cover_injected = _inject_cover(volume_dir, dry_run)
    try:
        args = adapter.build_invocation(volume_dir, out_path, settings)
        logger.debug(f"kcc CLI args invocation: {args}")
        rc = adapter.run_module(args, dry_run=dry_run)
        if rc != 0:
            raise RuntimeError(f"kcc module returned non-zero exit code {rc}")
    finally:
        if cover_injected and not dry_run:
            _cleanup_cover_chapter(volume_dir)
    return out_path
