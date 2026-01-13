"""Convertor package: thin wrapper around Kindle Comic Converter (KCC).

Public API:
- convert_volume(volume_dir: Path, out_path: Optional[Path]=None, *, options: dict=None)

This package prefers invoking KCC as an importable module (runpy.run_module) and falls back
to invoking the `kcc` CLI via subprocess when import-based execution is not available.
"""
from pathlib import Path
from .kcc_adapter import convert_volume as _convert_volume


def convert_volume(volume_dir: Path, out_path: Path | None = None, *, options: dict | None = None):
    """Convert a volume directory into a kepub.epub file using KCC.

    Args:
        volume_dir: path to the folder holding the volume images (and possibly `.cbz` already extracted files).
        out_path: destination path for the generated `.kepub.epub`. If omitted, defaults to ``volume_dir.with_suffix('.kepub.epub')``.
        options: adapter options passed to KCC (boolean flags like ``manga_mode``, ``stretch``, ``color``, ``crop``).

    Returns the path to the generated file on success.
    Raises subprocess.CalledProcessError or RuntimeError on failure.
    """
    volume_dir = Path(volume_dir)
    if out_path is None:
        out_path = volume_dir.with_suffix(volume_dir.suffix + '.kepub.epub')
    return _convert_volume(volume_dir, Path(out_path), options or {})
