import subprocess
import sys
from pathlib import Path
import textwrap
import os


def run_convertor(tmp_path: Path, args):
    # Run the package CLI via `-m` and ensure the repository root is on PYTHONPATH
    repo_root = str(Path(__file__).resolve().parents[2])
    cmd = [sys.executable, '-m', 'convertor.cli'] + args
    env = os.environ.copy()
    env['PYTHONPATH'] = repo_root
    res = subprocess.run(cmd,
                         capture_output=True,
                         text=True,
                         env=env)
    return res


def make_vol(tmp_path: Path, name: str):
    vol = tmp_path / name
    vol.mkdir()
    # add an image file to make it non-empty
    (vol / '001.jpg').write_text('img')
    return vol

def test_skips_existing_output(tmp_path: Path, monkeypatch):
    root = tmp_path / 'root'
    root.mkdir()
    vol = make_vol(root, 'Series v01')
    out = vol.with_suffix(vol.suffix + '.kepub.epub')
    out.write_text('existing')

    res = run_convertor(tmp_path, [str(root)])
    assert res.returncode == 0
    assert 'skipping existing output' in (res.stdout + res.stderr)

def test_dry_run_shows_actions(tmp_path: Path):
    root = tmp_path / 'root'
    root.mkdir()
    vol = make_vol(root, 'Series v01')
    res = run_convertor(tmp_path, [str(root), '--dry-run'])
    assert res.returncode == 0
    print(f"stdout: {res.stdout}")
    print(f"stderr: {res.stderr}")
    assert 'generated' in res.stderr
    assert 'Series v01.kepub.epub' in res.stderr

# def test_works(tmp_path: Path, monkeypatch):
#     root = tmp_path / 'root'
#     root.mkdir()
#     vol = make_vol(root, 'Series v02')

#     res = run_convertor(tmp_path, [str(root)])
#     assert res.returncode == 0
#     print(f"stdout: {res.stdout}")
#     print(f"stder: {res.stderr}")
#     assert 'generated * Series v02.epub.kepub' in res.stderr


# def test_force_regen_calls_convert(monkeypatch, tmp_path: Path):
#     root = tmp_path / 'root'
#     root.mkdir()
#     vol = make_vol(root, 'Series v01')
#     out = vol.with_suffix(vol.suffix + '.kepub.epub')
#     out.write_text('existing')

#     called = {}

#     def fake_convert_volume(volume_dir, out_path, options=None):
#         called['args'] = (str(volume_dir), str(out_path), options)
#         # touch output file to emulate behavior
#         Path(out_path).write_text('generated')
#         return out_path

#     # patch the convertor.convert_volume used by cli
#     import importlib
#     import sys
#     repo_root = str(Path(__file__).resolve().parents[2])
#     sys.path.insert(0, repo_root)
#     import convertor
#     importlib.reload(convertor)
#     monkeypatch.setattr(convertor, 'convert_volume', fake_convert_volume)
#     # ensure subprocess run uses the same PYTHONPATH
#     os.environ['PYTHONPATH'] = repo_root

#     res = run_convertor(tmp_path, [str(root), '--force-regen'])

#     print(f"output: {out.read_text()}")
#     assert res.returncode == 0

#     assert 'generated' in out.read_text()
#     assert 'generated:' in (res.stdout + res.stderr)
