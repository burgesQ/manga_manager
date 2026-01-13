from pathlib import Path

from packer.utils import make_cbz, run_packer


def test_dry_run_no_files_moved(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()

    # create two cbz
    make_cbz(src, "Chapter 1.cbz")
    make_cbz(src, "Chapter 2.cbz")

    # run in dry-run with multiple workers
    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--verbose",
            "--serie",
            "TestSerie",
            "--volume",
            "1",
            "--chapter-range",
            "1,2",
            "--nb-worker",
            "4",
            "--dry-run",
        ],
    )
    assert (
        res.returncode == 0
    ), f"packer failed: stdout={res.stdout} stderr={res.stderr}"

    # original files must still be present
    assert (src / "Chapter 1.cbz").exists()
    assert (src / "Chapter 2.cbz").exists()

    # volume dir must NOT be created in dry-run; dest defaults to --path (src)
    volume_dir = src / "TestSerie v01"
    assert not volume_dir.exists()


def test_concurrent_move_and_extract(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()

    # create multiple cbz files to encourage concurrency
    for i in range(1, 9):
        make_cbz(src, f"Chapter {i}.cbz")

    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "TestSerie",
            "--volume",
            "2",
            "--chapter-range",
            "1..8",
            "--nb-worker",
            "4",
        ],
    )
    assert (
        res.returncode == 0
    ), f"packer failed: stdout={res.stdout} stderr={res.stderr}"

    volume_dir = src / "TestSerie v02"
    assert volume_dir.exists()

    # original files should be moved into volume dir
    for i in range(1, 9):
        orig = src / f"Chapter {i}.cbz"
        assert not orig.exists(), f"source file still exists: {orig}"

    # archive should be present inside volume dir and extracted into Chapter XXX dirs
    for i in range(1, 9):
        moved = volume_dir / f"Chapter {i}.cbz"
        assert moved.exists(), f"moved archive not found: {moved}"
        chapter_dir = volume_dir / f"Chapter {i:03d}"
        assert chapter_dir.exists(), f"chapter dir not found: {chapter_dir}"
        # check extracted files
        assert (
            chapter_dir / "001.jpg"
        ).exists(), f"extracted image missing: {chapter_dir}"
        assert (
            chapter_dir / "ComicInfo.xml"
        ).exists(), f"ComicInfo.xml missing in {chapter_dir}"
