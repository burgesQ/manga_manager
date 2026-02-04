from pathlib import Path
import sys
import pytest

from convertor.kcc_adapter import KCCAdapter, KCCInvocation


def test_build_invocation(tmp_path: Path):
    adapter = KCCAdapter()
    input_dir = tmp_path / "vol"
    input_dir.mkdir()
    out = tmp_path / "out.kepub.epub"
    inv = adapter.build_invocation(input_dir, out)
    assert isinstance(inv, KCCInvocation)
    args = inv.args
    assert "-o" in args
    assert str(out) in args
    assert "--manga-style" in args


def test_run_module_success_and_failure(tmp_path: Path):
    td = tmp_path / "kccmod"
    td.mkdir()
    file = td / "kcc.py"
    # success
    file.write_text("import sys\nsys.exit(0)\n")
    sys.path.insert(0, str(td))
    adapter = KCCAdapter()
    inv = adapter.build_invocation(td, tmp_path / "out.epub")
    try:
        rc = adapter.run_module(inv)
        assert rc == 0
        # simulate failure in a different module (avoid runpy caching issues)
        fail_file = td / "kcc_fail.py"
        fail_file.write_text("import sys\nsys.exit(3)\n")
        adapter.MODULE_NAME = "kcc_fail"
        with pytest.raises(RuntimeError):
            adapter.run_module(inv)
    finally:
        sys.path.pop(0)
