import subprocess
import sys
import zipfile
from pathlib import Path

from packer.utils import (
    run_packer,
    make_cbz
)

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
