import sys
import os
from pathlib import Path
import pytest

from convertor.kcc_adapter import KCCAdapter


def test_kcc_uses_kcc_c2e_executable_when_present(tmp_path: Path, monkeypatch):
    # create a fake kcc-c2e executable and ensure PATH includes it
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
