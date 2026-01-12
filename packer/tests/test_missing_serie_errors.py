import subprocess
import sys
import zipfile
from pathlib import Path


def run_packer(tmp_path: Path, args):
    script = Path(__file__).resolve().parents[1] / 'src' / 'packer' / 'main.py'
    cmd = [sys.executable, str(script)] + args
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res


def make_cbz(path: Path, name: str):
    p = path / name
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr('ComicInfo.xml', '<ComicInfo></ComicInfo>')
        z.writestr('001.jpg', 'img')
    return p


def test_missing_serie_errors(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()
    # create Chapter 1
    make_cbz(src, 'Chapter 1.cbz')

    res = run_packer(tmp_path, [
        '--path', str(src),
        '--volume', '1',
        '--chapter-range', '1',
    ])
    assert res.returncode == 2
    out = (res.stderr or res.stdout)
    assert 'either --serie or a `serie` key in packer.json must be provided' in out
