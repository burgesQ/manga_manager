import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import convertor


def _make_executable(path: Path, exit_code: int = 0):
    path.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    st = path.stat()
    path.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_cli_fallback_to_external_executable_end_to_end(
    tmp_path: Path, make_vol, run_convertor
):
    root = tmp_path / "root"
    root.mkdir()
    make_vol(root, "Series v01")

    pkg_parent = tmp_path / "pkgs"
    pkg_parent.mkdir()
    pkg = pkg_parent / "kindlecomicconverter"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# stub package without __main__")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "kcc-c2e"
    _make_executable(exe, exit_code=0)

    extra_env = {
        "PYTHONPATH": str(pkg_parent) + os.pathsep + os.environ.get("PYTHONPATH", ""),
        "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
    }

    res = run_convertor(root, args=["--loglevel", "DEBUG"], extra_env=extra_env)
    print("stdout:", res.stdout)
    print("stderr:", res.stderr)
    assert res.returncode == 0
    assert "generated:" in (res.stdout + res.stderr)


def test_convert_volume_raises_if_package_unexecutable_and_no_exec(
    tmp_path: Path, make_vol
):
    root = tmp_path / "root"
    root.mkdir()
    make_vol(root, "Series v01")

    pkg_parent = tmp_path / "pkgs"
    pkg_parent.mkdir()
    pkg = pkg_parent / "kindlecomicconverter"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# stub package without __main__")

    sys.path.insert(0, str(pkg_parent))
    try:
        with pytest.raises((FileNotFoundError, subprocess.CalledProcessError)):
            convertor.convert_volume(root / "Series v01", None)
    finally:
        sys.path.pop(0)
