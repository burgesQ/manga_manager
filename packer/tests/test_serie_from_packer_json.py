import json
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


def test_serie_can_be_provided_via_packer_json(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()
    # provide serie via packer.json
    cfg = {'serie': 'FromConfig'}
    (src / 'packer.json').write_text(json.dumps(cfg))

    # create Chapter 1
    make_cbz(src, 'Chapter 1.cbz')

    res = run_packer(tmp_path, [
        '--path', str(src),
        '--volume', '1',
        '--chapter-range', '1',
    ])
    assert res.returncode == 0
    vol = src / 'FromConfig v01'
    assert vol.exists()
    assert (vol / 'Chapter 1.cbz').exists()
