import sys
from pathlib import Path
import pytest

from convertor.kcc_adapter import KCCAdapter


def test_fallback_to_alternative_module(tmp_path: Path):
    # Create an alternative module file that will act as the implementation
    td = tmp_path / "kccalt"
    td.mkdir()
    file = td / "kcc_alt.py"
    file.write_text("import sys\nsys.exit(0)\n")
    sys.path.insert(0, str(td))

    adapter = KCCAdapter()
    # Temporarily override the candidate list to include a non-existent name
    # first and then our alt module
    adapter.POSSIBLE_MODULE_NAMES = ("nonexistent_module_12345", "kcc_alt")

    inv = adapter.build_invocation(td, tmp_path / "out.epub")
    try:
        rc = adapter.run_module(inv)
        assert rc == 0
    finally:
        sys.path.pop(0)
