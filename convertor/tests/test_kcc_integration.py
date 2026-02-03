import shutil
from pathlib import Path
import pytest
import importlib.util

from convertor.kcc_adapter import convert_volume


def prepare_volume(tmp_path: Path) -> Path:
    vol = tmp_path / "vol"
    vol.mkdir()
    # create minimal image files expected by KCC
    (vol / "001.jpg").write_bytes(b"img1")
    (vol / "002.jpg").write_bytes(b"img2")
    return vol


def test_convert_volume_dry_run(tmp_path: Path):
    vol = prepare_volume(tmp_path)
    out = tmp_path / "out.kepub.epub"
    res = convert_volume(vol, out, dry_run=True)
    assert res == out
    assert not out.exists()


@pytest.mark.skipif(importlib.util.find_spec("kcc") is None, reason="kcc module not importable")
def test_convert_volume_integration(tmp_path: Path):
    # If `kcc` is installed as an executable, we attempt the module invocation
    # (this will also work when kcc is importable as a module). If not present, skip.
    vol = prepare_volume(tmp_path)
    out = tmp_path / "out.kepub.epub"
    # Should run (or raise a RuntimeError if module exits non-zero)
    res = convert_volume(vol, out, dry_run=False)
    assert res == out
    assert out.exists()
