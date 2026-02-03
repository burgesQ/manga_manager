"""Small helpers exported for tests.

These convenience functions are intended for use by the test suite only.
"""
from pathlib import Path
import subprocess
import sys


def run_packer(tmp_path: Path, args):
    script = Path(__file__).resolve().parent / "main.py"
    cmd = [sys.executable, str(script)] + args
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res


def make_cbz(path: Path, name: str, include_comicinfo: bool = True):
    import zipfile

    p = path / name
    with zipfile.ZipFile(p, "w") as z:
        if include_comicinfo:
            z.writestr("ComicInfo.xml", "<ComicInfo></ComicInfo>")
        z.writestr("001.jpg", "img")
    return p
