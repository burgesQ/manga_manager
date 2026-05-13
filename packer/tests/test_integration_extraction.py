"""Integration tests for real .cbz extraction (no dry-run).

These tests exercise the full packer pipeline — move archives into volume dirs,
extract chapter contents — using actual filesystem operations rather than
simulations. Each test creates real .cbz files, runs packer without --dry-run,
and verifies that extracted chapter subdirs and their contents exist on disk.
"""

from pathlib import Path

import pytest


@pytest.mark.integration
def test_single_volume_extraction(tmp_path: Path, make_cbz, run_packer):
    """N chapters are extracted into Chapter NNN/ subdirs inside the volume dir."""
    src = tmp_path / "src"
    src.mkdir()

    # Create three chapter archives using the default "Chapter N" naming scheme
    for i in range(1, 4):
        make_cbz(src, f"Chapter {i}.cbz")

    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "TestSerie",
            "--volume",
            "1",
            "--chapter-range",
            "1..3",
        ],
    )
    assert (
        res.returncode == 0
    ), f"packer failed: stdout={res.stdout!r} stderr={res.stderr!r}"

    volume_dir = src / "TestSerie v01"
    assert volume_dir.exists(), f"volume dir not created: {volume_dir}"

    for i in range(1, 4):
        # Original archive must have been moved (no longer in src root)
        orig = src / f"Chapter {i}.cbz"
        assert not orig.exists(), f"source file was not moved: {orig}"

        # Archive must be present inside the volume dir
        moved_archive = volume_dir / f"Chapter {i}.cbz"
        assert (
            moved_archive.exists()
        ), f"archive not found in volume dir: {moved_archive}"

        # Extracted chapter subdir must exist with the canonical zero-padded name
        chapter_dir = volume_dir / f"Chapter {i:03d}"
        assert chapter_dir.exists(), f"chapter dir not created: {chapter_dir}"

        # Both files written by make_cbz must be present after extraction
        assert (
            chapter_dir / "001.jpg"
        ).exists(), f"extracted image missing in {chapter_dir}"
        assert (
            chapter_dir / "ComicInfo.xml"
        ).exists(), f"ComicInfo.xml missing in {chapter_dir}"


@pytest.mark.integration
def test_chapter_extras_extracted_alongside_main(tmp_path: Path, make_cbz, run_packer):
    """Extra chapters (16.1, 16.2) are extracted in numeric order alongside chapter 16."""
    src = tmp_path / "src"
    src.mkdir()

    # Create main chapter and two extra chapters
    make_cbz(src, "Chapter 16.cbz")
    make_cbz(src, "Chapter 16.1.cbz")
    make_cbz(src, "Chapter 16.2.cbz")

    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "ExtrasTest",
            "--volume",
            "3",
            "--chapter-range",
            "16",
        ],
    )
    assert (
        res.returncode == 0
    ), f"packer failed: stdout={res.stdout!r} stderr={res.stderr!r}"

    volume_dir = src / "ExtrasTest v03"
    assert volume_dir.exists(), f"volume dir not created: {volume_dir}"

    # All three archives must have been moved into the volume dir
    assert (volume_dir / "Chapter 16.cbz").exists()
    assert (volume_dir / "Chapter 16.1.cbz").exists()
    assert (volume_dir / "Chapter 16.2.cbz").exists()

    # None of the originals should remain at the source location
    assert not (src / "Chapter 16.cbz").exists()
    assert not (src / "Chapter 16.1.cbz").exists()
    assert not (src / "Chapter 16.2.cbz").exists()

    # Main chapter dir
    main_dir = volume_dir / "Chapter 016"
    assert main_dir.exists(), f"main chapter dir not created: {main_dir}"
    assert (main_dir / "001.jpg").exists()
    assert (main_dir / "ComicInfo.xml").exists()

    # Extra chapter dirs use the canonical "Chapter NNN.suffix" naming
    extra1_dir = volume_dir / "Chapter 016.1"
    assert extra1_dir.exists(), f"extra chapter dir 016.1 not created: {extra1_dir}"
    assert (extra1_dir / "001.jpg").exists()
    assert (extra1_dir / "ComicInfo.xml").exists()

    extra2_dir = volume_dir / "Chapter 016.2"
    assert extra2_dir.exists(), f"extra chapter dir 016.2 not created: {extra2_dir}"
    assert (extra2_dir / "001.jpg").exists()
    assert (extra2_dir / "ComicInfo.xml").exists()


@pytest.mark.integration
def test_batch_processing_creates_two_volumes(tmp_path: Path, make_cbz, run_packer):
    """--batch 'v01:1..3-v02:4..6' creates two volume dirs each with correct chapter subdirs."""
    src = tmp_path / "src"
    src.mkdir()

    # Create six chapter archives for two volumes
    for i in range(1, 7):
        make_cbz(src, f"Chapter {i}.cbz")

    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "BatchSerie",
            "--batch",
            "v01:1..3-v02:4..6",
        ],
    )
    assert (
        res.returncode == 0
    ), f"packer failed: stdout={res.stdout!r} stderr={res.stderr!r}"

    # --- Verify volume 01 ---
    vol1_dir = src / "BatchSerie v01"
    assert vol1_dir.exists(), f"volume 01 dir not created: {vol1_dir}"

    for i in range(1, 4):
        orig = src / f"Chapter {i}.cbz"
        assert not orig.exists(), f"source file was not moved: {orig}"

        archive = vol1_dir / f"Chapter {i}.cbz"
        assert archive.exists(), f"archive missing from vol01: {archive}"

        chapter_dir = vol1_dir / f"Chapter {i:03d}"
        assert chapter_dir.exists(), f"chapter dir missing in vol01: {chapter_dir}"
        assert (chapter_dir / "001.jpg").exists()
        assert (chapter_dir / "ComicInfo.xml").exists()

    # --- Verify volume 02 ---
    vol2_dir = src / "BatchSerie v02"
    assert vol2_dir.exists(), f"volume 02 dir not created: {vol2_dir}"

    for i in range(4, 7):
        orig = src / f"Chapter {i}.cbz"
        assert not orig.exists(), f"source file was not moved: {orig}"

        archive = vol2_dir / f"Chapter {i}.cbz"
        assert archive.exists(), f"archive missing from vol02: {archive}"

        chapter_dir = vol2_dir / f"Chapter {i:03d}"
        assert chapter_dir.exists(), f"chapter dir missing in vol02: {chapter_dir}"
        assert (chapter_dir / "001.jpg").exists()
        assert (chapter_dir / "ComicInfo.xml").exists()

    # Cross-check: no chapter from vol02 leaked into vol01 and vice-versa
    for i in range(4, 7):
        assert not (
            vol1_dir / f"Chapter {i:03d}"
        ).exists(), f"chapter {i} leaked into vol01"
    for i in range(1, 4):
        assert not (
            vol2_dir / f"Chapter {i:03d}"
        ).exists(), f"chapter {i} leaked into vol02"
