from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# convertor.cli imports setup_logging from packer; make packer importable
# when running convertor tests in isolation from the convertor/ directory.
_packer_src = Path(__file__).resolve().parents[2] / "packer" / "src"
if str(_packer_src) not in sys.path:
    sys.path.insert(0, str(_packer_src))


def _make_vol(root: Path, name: str = "Series v01") -> Path:
    vol = root / name
    vol.mkdir(parents=True, exist_ok=True)
    (vol / "001.jpg").write_text("img")
    return vol


def _run_convertor(
    root: Path,
    args: list[str] | None = None,
    extra_env: dict | None = None,
) -> subprocess.CompletedProcess:
    repo_root = str(Path(__file__).resolve().parents[2])
    cmd = [sys.executable, "-m", "convertor.cli"] + (args or []) + [str(root)]
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        repo_root
        + os.pathsep
        + os.path.join(repo_root, "convertor", "src")
        + os.pathsep
        + os.path.join(repo_root, "packer", "src")
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


@pytest.fixture
def make_vol():
    return _make_vol


@pytest.fixture
def run_convertor():
    return _run_convertor
