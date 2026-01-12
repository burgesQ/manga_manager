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


def test_extra_chapter_assigned_to_base(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()

    # create main and extra
    make_cbz(src, 'Ch.013.cbz')
    make_cbz(src, 'Ch.013.5.cbz')

    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'Mashle',
        '--volume', '1',
        '--chapter-range', '13',
    ])
    assert res.returncode == 0, f"packer failed: stdout={res.stdout} stderr={res.stderr}"

    volume_dir = src / 'Mashle v01'
    assert volume_dir.exists()

    # both the main archive and the extra archive should be moved there
    assert (volume_dir / 'Ch.013.cbz').exists()
    assert (volume_dir / 'Ch.013.5.cbz').exists()

    # both chapter dirs exist: Chapter 013 and Chapter 013.5
    assert (volume_dir / 'Chapter 013').exists()
    assert (volume_dir / 'Chapter 013.5').exists()
