    #!/usr/bin/env python3
"""Entry point shim for the packer CLI."""
from __future__ import annotations

import sys
from pathlib import Path

# When executed as a script the package may not be importable using relative
# imports. Ensure the package `src` directory is on sys.path so absolute
# imports like `import packer.core` work when running this file directly.
_pkg_src = str(Path(__file__).resolve().parent.parent)
if _pkg_src not in sys.path:
    sys.path.insert(0, _pkg_src)

# Re-export a selection of core helpers for compatibility (use absolute imports)


# Expose CLI entry point
from packer.cli import main


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))








# Legacy implementation removed. Implementation lives in `packer.cli`, `packer.core` and `packer.worker`.
# This module intentionally only re-exports a small set of helper functions for
# backwards compatibility and exposes the CLI entry point `main`.
