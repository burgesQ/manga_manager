"""Editor package: thin wrapper around eboolib to edit epub files metadata.

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

from editor.cli import main

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
