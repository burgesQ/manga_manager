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


def test_batch_multiple_volumes(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()

    # volume 1 chapters 1-3
    for i in range(1, 4):
        make_cbz(src, f'Chapter {i}.cbz')
    # volume 2 chapters 4-6
    for i in range(4, 7):
        make_cbz(src, f'Chapter {i}.cbz')

    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'BatchSerie',
        '--batch', 'v01:1..3-v02:4..6',
        '--nb-worker', '3'
    ])
    assert res.returncode == 0, f"packer failed: stdout={res.stdout} stderr={res.stderr}"

    vol1 = src / 'BatchSerie v01'
    vol2 = src / 'BatchSerie v02'
    assert vol1.exists()
    assert vol2.exists()

    for i in range(1, 4):
        assert (vol1 / f'Chapter {i}.cbz').exists() or (vol1 / f'Chapter {i:03d}').exists()
    for i in range(4, 7):
        assert (vol2 / f'Chapter {i}.cbz').exists() or (vol2 / f'Chapter {i:03d}').exists()
