import os
from pathlib import Path

from packer.cli import Config
from packer.testing import make_cbz
from packer.worker import process_one, process_volume


def make_plain_file(path: Path, name: str):
    p = path / name
    p.write_text("plain")
    return str(p)


def test_process_one_normal(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()

    src_file = make_cbz(src, "Chapter 1.cbz")

    cfg = Config(
        path=str(src),
        dest=str(dest),
        serie="S",
        volume=1,
        chapter_range=[1],
        nb_worker=1,
        dry_run=False,
        verbose=False,
        force=False,
    )

    cid, moved = process_one("1", src_file, cfg)
    assert cid == "1"
    # moved archive should be inside the volume dir
    assert os.path.exists(moved)
    assert not os.path.exists(src_file)
    # chapter dir must exist and contain extracted files
    chap_dir = dest / "S v01" / "Chapter 001"
    assert chap_dir.exists()
    assert (chap_dir / "001.jpg").exists()


def test_process_one_dry_run(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()

    src_file = make_cbz(src, "Chapter 2.cbz")

    cfg = Config(
        path=str(src),
        dest=str(dest),
        serie="S",
        volume=1,
        chapter_range=[2],
        nb_worker=1,
        dry_run=True,
        verbose=True,
        force=False,
    )

    cid, moved = process_one("2", src_file, cfg)
    assert cid == "2"
    # In dry-run the source file must not be moved and chapter dir not created
    assert os.path.exists(src_file)
    assert not (dest / "S v01" / "Chapter 002").exists()


def test_process_one_force_overwrite(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()

    src_file = make_cbz(src, "Chapter 3.cbz")

    # create an existing chapter dir with a marker file
    vol_dir = dest / "S v01"
    vol_dir.mkdir()
    chap_dir = vol_dir / "Chapter 003"
    chap_dir.mkdir()
    (chap_dir / "keep.txt").write_text("old")

    cfg = Config(
        path=str(src),
        dest=str(dest),
        serie="S",
        volume=1,
        chapter_range=[3],
        nb_worker=1,
        dry_run=False,
        verbose=False,
        force=True,
    )

    cid, moved = process_one("3", src_file, cfg)
    assert cid == "3"
    # the previous marker should be gone
    assert not (chap_dir / "keep.txt").exists()
    # new extracted file must be present
    assert (chap_dir / "001.jpg").exists()


def test_process_one_skip_if_chapter_exists(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()

    src_file = make_cbz(src, "Chapter 4.cbz")

    vol_dir = dest / "S v01"
    vol_dir.mkdir()
    chap_dir = vol_dir / "Chapter 004"
    chap_dir.mkdir()
    (chap_dir / "keep.txt").write_text("old")

    cfg = Config(
        path=str(src),
        dest=str(dest),
        serie="S",
        volume=1,
        chapter_range=[4],
        nb_worker=1,
        dry_run=False,
        verbose=False,
        force=False,
    )

    cid, moved = process_one("4", src_file, cfg)
    assert cid == "4"
    # file should be moved but because chapter existed and force=False
    # process_one returns early. The archive should have been moved into
    # volume dir even if extraction skipped
    assert (dest / "S v01" / "Chapter 4.cbz".lstrip()).exists() or (
        dest / "S v01" / "Chapter 4.cbz".replace("Chapter ", "Chapter ").lstrip()
    ).exists()
    # chapter dir original marker should still exist
    assert (chap_dir / "keep.txt").exists()


def test_process_volume_removes_moved_files(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()

    # create three chapters
    files = [make_cbz(src, f"Chapter {i}.cbz") for i in (1, 2, 3)]
    cfg = Config(
        path=str(src),
        dest=str(dest),
        serie="S",
        volume=1,
        chapter_range=[1, 2, 3],
        nb_worker=2,
        dry_run=False,
        verbose=False,
        force=False,
    )

    avail = list(files)
    rc, remaining = process_volume(1, [1, 2, 3], avail, cfg)
    assert rc == 0
    # moved files removed from remaining
    assert not remaining
    # archives moved into dest
    for i in (1, 2, 3):
        assert (dest / "S v01" / f"Chapter {i}.cbz").exists()


def test_process_volume_missing_chapter_returns_3(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()

    # create only chapter 1
    make_cbz(src, "Chapter 1.cbz")

    cfg = Config(
        path=str(src),
        dest=str(dest),
        serie="S",
        volume=1,
        chapter_range=[1, 2],
        nb_worker=1,
        dry_run=False,
        verbose=False,
        force=False,
    )

    avail = [str(p) for p in src.iterdir()]
    rc, remaining = process_volume(1, [1, 2], avail, cfg)
    assert rc == 3


def test_process_volume_duplicate_mains_returns_4(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()

    make_cbz(src, "Chapter 1.cbz")
    make_cbz(src, "Ch 01.cbz")

    cfg = Config(
        path=str(src),
        dest=str(dest),
        serie="S",
        volume=1,
        chapter_range=[1],
        nb_worker=1,
        dry_run=False,
        verbose=False,
        force=False,
    )

    avail = [str(p) for p in src.iterdir()]
    rc, remaining = process_volume(1, [1], avail, cfg)
    assert rc == 4
