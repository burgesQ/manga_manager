import subprocess
import sys
from pathlib import Path
import zipfile


def run_packer(tmp_path: Path, args):
    script = Path(__file__).resolve().parents[1] / 'src' / 'packer' / 'main.py'
    cmd = [sys.executable, str(script)] + args
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res


def make_cbz(path: Path, name: str, include_comicinfo: bool = True):
    p = path / name
    with zipfile.ZipFile(p, 'w') as z:
        if include_comicinfo:
            z.writestr('ComicInfo.xml', '<ComicInfo></ComicInfo>')
        z.writestr('001.jpg', 'img')
    return p


def test_invalid_regex_returns_2(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()
    make_cbz(src, 'Chapter 1.cbz')
    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'X',
        '--volume', '1',
        '--chapter-range', '1',
        '--chapter-regex', '(unclosed',
    ])
    assert res.returncode == 2
    assert 'Invalid regex' in res.stderr


def test_invalid_batch_spec_returns_2(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()
    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'X',
        '--batch', 'badspec'
    ])
    assert res.returncode == 2
    assert 'invalid batch spec' in res.stderr.lower()


def test_missing_args_returns_2(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()
    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'X'
    ])
    assert res.returncode == 2


def test_duplicate_mains_returns_4(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()
    make_cbz(src, 'Chapter 1.cbz')
    make_cbz(src, 'Ch 01.cbz')
    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'Dup',
        '--volume', '1',
        '--chapter-range', '1'
    ])
    assert res.returncode == 4
    assert 'multiple archives match chapter' in res.stderr.lower()


def test_missing_comicinfo_returns_6(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()
    make_cbz(src, 'Chapter 1.cbz', include_comicinfo=False)
    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'NoCI',
        '--volume', '1',
        '--chapter-range', '1'
    ])
    assert res.returncode == 6
    assert 'missing ComicInfo' in res.stderr or 'Missing ComicInfo' in res.stderr


def test_bad_zip_returns_6(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()
    p = src / 'Chapter 1.cbz'
    with open(p, 'wb') as fh:
        fh.write(b'not a zip')
    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'BadZip',
        '--volume', '1',
        '--chapter-range', '1'
    ])
    assert res.returncode == 6
    # depending on where the BadZipFile is detected, the tool may report a
    # missing ComicInfo or a Bad zip file error; accept either message
    assert ('Bad zip file' in res.stderr) or ('Missing ComicInfo' in res.stderr)


def test_path_traversal_detected(tmp_path: Path):
    src = tmp_path / 'src'
    src.mkdir()
    p = src / 'Chapter 1.cbz'
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr('../evil.txt', 'gotcha')
        z.writestr('ComicInfo.xml', '<ComicInfo></ComicInfo>')
    res = run_packer(tmp_path, [
        '--path', str(src),
        '--serie', 'Path',
        '--volume', '1',
        '--chapter-range', '1'
    ])
    assert res.returncode == 6
    assert 'Unsafe path' in res.stderr or 'Unsafe path' in res.stdout
