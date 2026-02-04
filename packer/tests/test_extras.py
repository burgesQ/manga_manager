from pathlib import Path



def test_extra_chapter_assigned_to_base(tmp_path: Path, make_cbz, run_packer):
    src = tmp_path / "src"
    src.mkdir()

    # create main and extra
    make_cbz(src, "Ch.013.cbz")
    make_cbz(src, "Ch.013.5.cbz")

    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "Mashle",
            "--volume",
            "1",
            "--chapter-range",
            "13",
        ],
    )
    assert res.returncode == 0, (
        f"packer failed: stdout={res.stdout} stderr={res.stderr}"
    )

    volume_dir = src / "Mashle v01"
    assert volume_dir.exists()

    # both the main archive and the extra archive should be moved there
    assert (volume_dir / "Ch.013.cbz").exists()
    assert (volume_dir / "Ch.013.5.cbz").exists()

    # both chapter dirs exist: Chapter 013 and Chapter 013.5
    assert (volume_dir / "Chapter 013").exists()
    assert (volume_dir / "Chapter 013.5").exists()
