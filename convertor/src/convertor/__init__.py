"""Convertor package: thin wrapper around Kindle Comic Converter (KCC).

Public API:
- convert_volume(volume_dir: Path, out_path: Optional[Path]=None, *, options: dict=None)

This package prefers invoking KCC as an importable module (runpy.run_module) and falls back
to invoking the `kcc` CLI via subprocess when import-based execution is not available.
"""
from pathlib import Path
from .kcc_adapter import convert_volume as _convert_volume


def convert_volume(volume_dir: Path, out_path: Path | None = None, *, dry_run: bool = False):
    """Convert a volume directory into a kepub.epub file using KCC.

    Args:
        volume_dir: path to the folder holding the volume images (and possibly `.cbz` already extracted files).
        out_path: destination path for the generated `.kepub.epub`. If omitted, defaults to ``volume_dir.with_suffix('.kepub.epub')``.
        dry_run: if True, do not execute the conversion (dry run).

    Returns the path to the generated file on success.
    Raises subprocess.CalledProcessError or RuntimeError on failure.
    """
    volume_dir = Path(volume_dir)
    # default output: sibling file next to the volume dir with a predictable name
    if out_path is None:
        out_path = volume_dir.parent / (volume_dir.name + '.kepub.epub')
    return _convert_volume(volume_dir, Path(out_path), dry_run=dry_run)
