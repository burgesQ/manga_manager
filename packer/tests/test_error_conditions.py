import zipfile
from pathlib import Path

from packer.tests.conftest import make_cbz, run_packer


def test_invalid_regex_returns_2(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    make_cbz(src, "Chapter 1.cbz")
    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "X",
            "--volume",
            "1",
            "--chapter-range",
            "1",
            "--chapter-regex",
            "(unclosed",
        ],
    )
    assert res.returncode == 2
    assert "Invalid regex" in res.stderr


def test_invalid_batch_spec_returns_2(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    res = run_packer(
        tmp_path, ["--path", str(src), "--serie", "X", "--batch", "badspec"]
    )
    assert res.returncode == 2
    assert "invalid batch spec" in res.stderr.lower()


def test_missing_args_returns_2(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    res = run_packer(tmp_path, ["--path", str(src), "--serie", "X"])
    assert res.returncode == 2


def test_duplicate_mains_returns_4(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    make_cbz(src, "Chapter 1.cbz")
    make_cbz(src, "Ch 01.cbz")
    res = run_packer(
        tmp_path,
        ["--path", str(src), "--serie", "Dup", "--volume", "1", "--chapter-range", "1"],
    )
    assert res.returncode == 4
    assert "multiple archives match chapter" in res.stderr.lower()


def test_missing_comicinfo_returns_6(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    make_cbz(src, "Chapter 1.cbz", include_comicinfo=False)
    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "NoCI",
            "--volume",
            "1",
            "--chapter-range",
            "1",
        ],
    )
    assert res.returncode == 6
    assert "missing ComicInfo" in res.stderr or "Missing ComicInfo" in res.stderr


def test_bad_zip_returns_6(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    p = src / "Chapter 1.cbz"
    with open(p, "wb") as fh:
        fh.write(b"not a zip")
    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "BadZip",
            "--volume",
            "1",
            "--chapter-range",
            "1",
        ],
    )
    assert res.returncode == 6
    # depending on where the BadZipFile is detected, the tool may report a
    # missing ComicInfo or a Bad zip file error; accept either message
    assert ("Bad zip file" in res.stderr) or ("Missing ComicInfo" in res.stderr)


def test_path_traversal_detected(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    p = src / "Chapter 1.cbz"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("../evil.txt", "gotcha")
        z.writestr("ComicInfo.xml", "<ComicInfo></ComicInfo>")
    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "Path",
            "--volume",
            "1",
            "--chapter-range",
            "1",
        ],
    )
    assert res.returncode == 6
    assert "Unsafe path" in res.stderr or "Unsafe path" in res.stdout
