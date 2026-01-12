import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


def make_cbz(path: Path, name: str, include_comicinfo: bool = True):
    p = path / name
    with zipfile.ZipFile(p, 'w') as z:
        if include_comicinfo:
            z.writestr('ComicInfo.xml', '<ComicInfo></ComicInfo>')
        z.writestr('001.jpg', 'fakeimagecontent')
    return p


def run_packer(tmp_path: Path, args):
    script = Path(__file__).resolve().parents[1] / 'src' / 'packer' / 'main.py'
    cmd = [sys.executable, str(script)] + args
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res


def test_named_pattern_mashle(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()

    make_cbz(src, 'Ch.013.cbz')
    make_cbz(src, 'Ch.013.5.cbz')

    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'Mashle',
        '--volume', '1',
        '--chapter-range', '13',
        '--pattern', 'mashle'
    ])
    assert res.returncode == 0, f"packer failed: stdout={res.stdout} stderr={res.stderr}"

    vol = src / 'Mashle v01'
    assert vol.exists()
    assert (vol / 'Ch.013.cbz').exists()
    assert (vol / 'Ch.013.5.cbz').exists()


def test_custom_regex_override(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()

    make_cbz(src, 'X_013.cbz')
    make_cbz(src, 'X_014.cbz')

    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'Custom',
        '--volume', '1',
        '--chapter-range', '13..14',
        '--chapter-regex', r'(?i)X_0*([0-9]+)'
    ])
    assert res.returncode == 0, f"packer failed: stdout={res.stdout} stderr={res.stderr}"

    vol = src / 'Custom v01'
    assert vol.exists()
    assert (vol / 'X_013.cbz').exists()
    assert (vol / 'X_014.cbz').exists()
