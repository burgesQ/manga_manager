import os
import stat
import subprocess
from pathlib import Path
import runpy
import shlex
import sys
import pytest

from convertor.kcc_adapter import KCCAdapter


def _make_executable(path: Path, exit_code: int = 0):
    # Create a simple shell script that exits with `exit_code` and mark it executable
    path.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    st = path.stat()
    path.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_fallback_to_external_executable_success(tmp_path: Path, monkeypatch):
    # Create a fake external CLI in a temp bin dir and ensure PATH includes it
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "kcc-c2e"
    _make_executable(exe, exit_code=0)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    adapter = KCCAdapter()
    inv = adapter.build_invocation(tmp_path, tmp_path / "out.epub")

    rc = adapter.run_module(inv)
    assert rc == 0


def test_fallback_to_external_executable_failure(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "kcc-c2e"
    _make_executable(exe, exit_code=3)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    adapter = KCCAdapter()
    inv = adapter.build_invocation(tmp_path, tmp_path / "out.epub")

    with pytest.raises(subprocess.CalledProcessError):
        adapter.run_module(inv)
