import sys
from pathlib import Path

# convertor.cli imports setup_logging from packer; make packer importable
# when running convertor tests in isolation from the convertor/ directory.
_packer_src = Path(__file__).resolve().parents[2] / "packer" / "src"
if str(_packer_src) not in sys.path:
    sys.path.insert(0, str(_packer_src))
