import os
import sys
import stat
import subprocess
from pathlib import Path

import pytest

import convertor


def _make_executable(path: Path, exit_code: int = 0):
    path.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    st = path.stat()
    path.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def run_convertor_subprocess(root: Path, extra_env: dict | None = None, args: list[str] | None = None):
    repo_root = str(Path(__file__).resolve().parents[2])
    cmd = [sys.executable, "-m", "convertor.cli"] + (args or []) + [str(root)]
    env = os.environ.copy()
    # Ensure package src and packer src are on PYTHONPATH so -m convertor.cli works
    env["PYTHONPATH"] = repo_root + os.pathsep + os.path.join(repo_root, "convertor", "src") + os.pathsep + os.path.join(repo_root, "packer", "src")
    if extra_env:
        env.update(extra_env)
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def test_cli_fallback_to_external_executable_end_to_end(tmp_path: Path):
    # Create a sample volume
    root = tmp_path / "root"
    root.mkdir()
    vol = root / "Series v01"
    vol.mkdir()
    (vol / "001.jpg").write_text("img")

    # Make a package that is importable but lacks a runnable __main__ (simulates package-only install)
    pkg_parent = tmp_path / "pkgs"
    pkg_parent.mkdir()
    pkg = pkg_parent / "kindlecomicconverter"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# stub package without __main__")

    # Create a fake external executable named 'kcc-c2e' (that's what the adapter invokes)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "kcc-c2e"
    _make_executable(exe, exit_code=0)

    # Run the CLI with PYTHONPATH including our package and PATH pointing to bin dir
    extra_env = {"PYTHONPATH": str(pkg_parent) + os.pathsep + os.environ.get("PYTHONPATH", ""), "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", "")}

    res = run_convertor_subprocess(root, extra_env=extra_env, args=["--loglevel", "DEBUG"])
    print("stdout:", res.stdout)
    print("stderr:", res.stderr)
    assert res.returncode == 0
    # CLI logs 'generated:' upon successful convert_volume return
    assert "generated:" in (res.stdout + res.stderr)


def test_convert_volume_raises_if_package_unexecutable_and_no_exec(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    vol = root / "Series v01"
    vol.mkdir()
    (vol / "001.jpg").write_text("img")

    # Create an importable package without __main__ and ensure PATH has no executable
    pkg_parent = tmp_path / "pkgs"
    pkg_parent.mkdir()
    pkg = pkg_parent / "kindlecomicconverter"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# stub package without __main__")

    # Ensure our package parent is on sys.path for this test process
    sys.path.insert(0, str(pkg_parent))
    try:
        # Adapter currently invokes the external 'kcc-c2e' directly; when it is
        # missing subprocess.run will raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            convertor.convert_volume(vol, None)
    finally:
        sys.path.pop(0)
