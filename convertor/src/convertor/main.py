"""Convertor package: thin wrapper around Kindle Comic Converter (KCC).

Public API:
- convert_volume(volume_dir: Path, out_path: Optional[Path]=None, *, options: dict=None)

This package prefers invoking KCC as an importable module (runpy.run_module) and falls back
to invoking the `kcc` CLI via subprocess when import-based execution is not available.
"""
from __future__ import annotations

import sys
from pathlib import Path
# When executed as a script the package may not be importable using relative
# imports. Ensure the package `src` directory is on sys.path so absolute
# imports like `import packer.core` work when running this file directly.
_pkg_src = str(Path(__file__).resolve().parent.parent)
if _pkg_src not in sys.path:
    sys.path.insert(0, _pkg_src)

from convertor.cli import main

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
