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


def test_config_json_applies_defaults(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()
    # put a packer.json config with pattern fma and a batch file
    cfg = {
        'pattern': 'fma'
    }
    (src / 'packer.json').write_text(json.dumps(cfg))

    # create Chapter 16 and extras
    make_cbz(src, 'Chap 16.cbz')
    make_cbz(src, 'Chap 16.1.cbz')

    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'FMAConfig',
        '--volume', '1',
        '--chapter-range', '16',
    ])
    assert res.returncode == 0
    vol = src / 'FMAConfig v01'
    assert vol.exists()
    assert (vol / 'Chap 16.cbz').exists()
    assert (vol / 'Chap 16.1.cbz').exists()
