import sys
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

    # simulate runpy.run_module executing and not raising SystemExit
    monkeypatch.setattr('runpy.run_module', lambda name, run_name=None: None)

    # Make a dummy importable 'kcc' module so the adapter resolves at init time
    from importlib.machinery import ModuleSpec
    mod = types.ModuleType('kcc')
    mod.__spec__ = ModuleSpec('kcc', loader=None)
    sys.modules['kcc'] = mod

    vol = tmp_path / 'Vol'
    vol.mkdir()
    out = tmp_path / 'Vol.kepub.epub'

    try:
        # call the adapter; should return the output path
        res = kcc_adapter.convert_volume(vol, out, dry_run=False)
        assert res == out
    finally:
        del sys.modules['kcc']
