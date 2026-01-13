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
import runpy
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

    # Target profile - use Kobo colour profile to match screenshot
    # Many KCC CLI accept "--profile" or "--device"; provide both possibilities.
    args.extend(['--device', 'kobo_libra_colour'])

    # Modes and flags (enable to match screenshot)
    if options.get('manga_mode', True):
        args.append('--manga-mode')
    if options.get('stretch', True):
        args.append('--stretch')
    if options.get('color', True):
        args.append('--color')
    if options.get('crop', True):
        args.append('--crop')

    # Input is directory
    args.append(str(input_dir))
    return args


def _run_module_kcc(args: list[str]) -> int:
    """Run KCC as a module by setting sys.argv and calling runpy.run_module.

    Returns an exit code (0 success).
    """
    prev_argv = sys.argv[:]
    try:
        sys.argv = ['kcc'] + args
        # run the kcc module as a script; it may call sys.exit internally
        runpy.run_module('kcc', run_name='__main__')
        return 0
    except SystemExit as e:
        return int(e.code or 0)
    finally:
        sys.argv = prev_argv


def _run_subprocess_kcc(args: list[str]) -> int:
    """Run the installed `kcc` CLI with the provided args.

    Returns the process returncode.
    """
    cmd = ['kcc'] + args
    logger.debug('Running kcc CLI: %s', shlex.join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    logger.debug('kcc stdout: %s', res.stdout)
    logger.debug('kcc stderr: %s', res.stderr)
    return res.returncode


def convert_volume(volume_dir: Path, out_path: Path, options: dict | None = None) -> Path:
    """Convert a volume folder into an EPUB/Kepub using KCC.

    Attempts to use the module approach first, then falls back to subprocess.
    On success returns the output path, otherwise raises subprocess.CalledProcessError.
    """
    options = options or {}
    args = _build_kcc_args(volume_dir, out_path, options)

    # Try module first
    try:
        rc = _run_module_kcc(args)
        if rc == 0:
            return out_path
        logger.warning('kcc module returned non-zero exit code %s; falling back to CLI', rc)
    except Exception as e:
        logger.debug('kcc module invocation failed: %s', e)

    # Fallback to subprocess
    rc = _run_subprocess_kcc(args)
    if rc != 0:
        raise subprocess.CalledProcessError(rc, ['kcc'] + args)
    return out_path
