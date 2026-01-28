"""Adapter for Kindle Comic Converter (KCC).

This adapter constructs a minimal set of arguments that matches the screenshot:
- Manga mode
- Stretch/Upscale
- Color mode
- Cropping mode
- Target profile: Kobo ("Kobo Libra Colour")

The adapter will first attempt to run KCC as a module (via runpy.run_module). If that
fails (no module installed), it will fall back to calling the `kcc` CLI via subprocess.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import shlex
import logging

logger = logging.getLogger(__name__)


def _build_kcc_args(input_dir: Path, out_path: Path, options: dict) -> list[str]:
    """Create a list of CLI args for kcc based on the requested options.

    Note: arguments chosen to be robust across CLI or module invocation. We pass
    flags likely supported by the kcc CLI. If KCC changes flags, the subprocess
    fallback will still attempt the same invocation.
    """
    args: list[str] = []
    # Output file
    args.extend(['-o', str(out_path)])

    # Target profile
    args.extend(['--profile', 'KoLC'])  # Kobo Libra Colour

    # # Target profile - use Kobo colour profile to match screenshot
    # # Many KCC CLI accept "--profile" or "--device"; provide both possibilities.
    # args.extend(['--device', 'kobo_libra_colour'])

    # Modes and flags (enable to match screenshot)
    if options.get('manga_mode', True):
        args.append('--manga-mode')
    if options.get('stretch', True):
        args.append('--stretch')
    if options.get('color', True):
        args.append('--forcecolor')
    if options.get('crop', True):
        args.append('--cropping=2')

    # Input is directory
    args.append(str(input_dir))
    return args



def convert_volume(
        volume_dir: Path,
        out_path: Path,
        options: dict | None = None,
        dry_run: bool = False,
        ) -> Path:
    """Convert a volume folder into an EPUB/Kepub using KCC.

    On success returns the output path, otherwise raises subprocess.CalledProcessError.
    """
    options = options or {}
    args = _build_kcc_args(volume_dir, out_path, options)

    # Use kcc-c2e which is the CLI command installed by kindlecomicconverter
    cmd = ['kcc-c2e'] + args
    logger.debug('Running kcc: %s', shlex.join(cmd))

    if dry_run:
        logger.info('Dry run - would execute: %s', shlex.join(cmd))
        return out_path

    res = subprocess.run(cmd, capture_output=True, text=True)

    if res.stdout:
        logger.debug('kcc stdout: %s', res.stdout)
    if res.stderr:
        logger.debug('kcc stderr: %s', res.stderr)

    if res.returncode != 0:
        raise subprocess.CalledProcessError(res.returncode, cmd, res.stdout, res.stderr)

    return out_path
