import subprocess
import sys
import zipfile
from pathlib import Path


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


def test_fma_extras_ordering(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()

    # main chapter and two extras
    make_cbz(src, 'Chap 16.cbz')
    make_cbz(src, 'Chap 16.2.cbz')
    make_cbz(src, 'Chap 16.1.cbz')

    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'FMA',
        '--volume', '1',
        '--chapter-range', '16',
        '--pattern', 'fma',
        '--verbose',
        '--nb-worker', '1'
    ])
    assert res.returncode == 0, f"packer failed: stdout={res.stdout} stderr={res.stderr}"

    vol = src / 'FMA v01'
    assert vol.exists()
    # ensure archives were moved
    assert (vol / 'Chap 16.cbz').exists()
    assert (vol / 'Chap 16.1.cbz').exists()
    assert (vol / 'Chap 16.2.cbz').exists()

    # check ordering in stdout: main before extras, and extras in numeric order
    out = res.stdout
    idx_main = out.find('processing chapter 16')
    idx_e1 = out.find('processing chapter 16.1')
    idx_e2 = out.find('processing chapter 16.2')
    assert idx_main != -1 and idx_e1 != -1 and idx_e2 != -1, f"missing log lines: {out}"
    assert idx_main < idx_e1 < idx_e2
