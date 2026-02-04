from pathlib import Path
import sys
import os
import subprocess
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


def test_run_module_success_and_failure(tmp_path: Path, monkeypatch):
    # Create a fake 'kcc-c2e' executable that succeeds
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "kcc-c2e"
    exe.write_text("#!/bin/sh\nexit 0\n")
    st = exe.stat()
    exe.chmod(st.st_mode | 0o111)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    adapter = KCCAdapter()
    inv = adapter.build_invocation(tmp_path, tmp_path / "out.epub")

    rc = adapter.run_module(inv)
    assert rc == 0

    # Now make the executable fail (non-zero exit) and assert subprocess.CalledProcessError
    exe.write_text("#!/bin/sh\nexit 3\n")
    st = exe.stat()
    exe.chmod(st.st_mode | 0o111)

    with pytest.raises(subprocess.CalledProcessError):
        adapter.run_module(inv)
