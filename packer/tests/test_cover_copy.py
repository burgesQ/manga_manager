"""Tests for cover image copying into volume directories."""

import logging
from pathlib import Path

from packer.types_ import CoverMapping
from packer.worker import process_volume


def test_cover_copied_to_volume_dir(tmp_path: Path, make_cbz, make_config):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    cbz = make_cbz(src, "Chapter 1.cbz")

    cover = tmp_path / "cover.webp"
    cover.write_bytes(b"webp_data")

    cfg = make_config(
        src,
        dest,
        serie="TestSerie",
        covers=[CoverMapping(volume=1, cover_path=str(cover))],
    )

    rc, _ = process_volume(1, [1], [str(cbz)], cfg)

    assert rc == 0
    volume_dir = dest / "TestSerie v01"
    assert (volume_dir / "cover.webp").exists()
    assert (volume_dir / "cover.webp").read_bytes() == b"webp_data"


def test_cover_missing_warns(tmp_path: Path, make_cbz, make_config, caplog):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    cbz = make_cbz(src, "Chapter 1.cbz")

    cfg = make_config(
        src,
        dest,
        serie="TestSerie",
        covers=[CoverMapping(volume=1, cover_path=str(tmp_path / "nonexistent.webp"))],
    )

    with caplog.at_level(logging.WARNING, logger="packer.worker"):
        rc, _ = process_volume(1, [1], [str(cbz)], cfg)

    assert rc == 0
    assert any("cover not found" in r.message for r in caplog.records)
    volume_dir = dest / "TestSerie v01"
    assert not (volume_dir / "cover.webp").exists()


def test_cover_dry_run(tmp_path: Path, make_cbz, make_config, caplog):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    cbz = make_cbz(src, "Chapter 1.cbz")

    cover = tmp_path / "cover.webp"
    cover.write_bytes(b"webp_data")

    cfg = make_config(
        src,
        dest,
        serie="TestSerie",
        dry_run=True,
        covers=[CoverMapping(volume=1, cover_path=str(cover))],
    )

    with caplog.at_level(logging.INFO, logger="packer.worker"):
        rc, _ = process_volume(1, [1], [str(cbz)], cfg)

    assert rc == 0
    assert any("DRY RUN" in r.message and "cover" in r.message for r in caplog.records)
    volume_dir = dest / "TestSerie v01"
    assert not (volume_dir / "cover.webp").exists()


def test_cover_skipped_when_no_mapping(tmp_path: Path, make_cbz, make_config):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    cbz = make_cbz(src, "Chapter 1.cbz")

    cfg = make_config(src, dest, serie="TestSerie", covers=None)

    rc, _ = process_volume(1, [1], [str(cbz)], cfg)

    assert rc == 0
    volume_dir = dest / "TestSerie v01"
    assert not (volume_dir / "cover.webp").exists()


def test_cover_only_applied_to_matching_volume(tmp_path: Path, make_cbz, make_config):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    cbz = make_cbz(src, "Chapter 1.cbz")

    cover = tmp_path / "cover.webp"
    cover.write_bytes(b"webp_data")

    cfg = make_config(
        src,
        dest,
        serie="TestSerie",
        covers=[CoverMapping(volume=2, cover_path=str(cover))],
    )

    rc, _ = process_volume(1, [1], [str(cbz)], cfg)

    assert rc == 0
    volume_dir = dest / "TestSerie v01"
    assert not (volume_dir / "cover.webp").exists()
