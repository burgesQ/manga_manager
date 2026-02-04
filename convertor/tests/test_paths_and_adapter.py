import sys
import os
from pathlib import Path
import subprocess
import types


def _ensure_importable_root():
    # Ensure the package's src folder is importable
    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / 'src'
    p = str(src_root)
    if p not in sys.path:
        sys.path.insert(0, p)


def test_default_output_path_and_delegate(tmp_path, monkeypatch):
    _ensure_importable_root()
    import convertor

    vol = tmp_path / 'Series v01'
    vol.mkdir()

    called = {}

    def fake_convert(v, out_path, dry_run=False, **kwargs):
        called['v'] = str(v)
        called['out'] = str(out_path)
        # create the file to simulate success
        Path(out_path).write_text('ok')
        return out_path

    # patch the package-level delegate used by `convertor.convert_volume`
    monkeypatch.setattr(convertor, '_convert_volume', fake_convert)

    out = convertor.convert_volume(vol)
    assert Path(called['out']).exists()
    assert Path(called['out']).name == 'Series v01.kepub.epub'


def test_kcc_adapter_module_invocation(tmp_path, monkeypatch):
    _ensure_importable_root()
    from convertor import kcc_adapter

    # Create a fake 'kcc-c2e' executable and ensure PATH includes it
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "kcc-c2e"
    exe.write_text("#!/bin/sh\nexit 0\n")
    st = exe.stat()
    exe.chmod(st.st_mode | 0o111)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    vol = tmp_path / 'Vol'
    vol.mkdir()
    out = tmp_path / 'Vol.kepub.epub'

    # call the adapter; should return the output path
    res = kcc_adapter.convert_volume(vol, out, dry_run=False)
    assert res == out
