"""Tests for cover injection helpers in kcc_adapter."""

from pathlib import Path
from unittest.mock import patch

from convertor.kcc_adapter import (
    COVER_CHAPTER_DIR,
    COVER_FILENAME,
    _cleanup_cover_chapter,
    _inject_cover,
    convert_volume,
)


def test_inject_cover_creates_chapter_000(tmp_path: Path):
    cover = tmp_path / COVER_FILENAME
    cover.write_bytes(b"webp_data")

    result = _inject_cover(tmp_path, dry_run=False)

    assert result is True
    chapter_dir = tmp_path / COVER_CHAPTER_DIR
    assert chapter_dir.is_dir()
    injected = chapter_dir / COVER_FILENAME
    assert injected.exists()
    assert injected.read_bytes() == b"webp_data"


def test_inject_cover_no_cover_file(tmp_path: Path):
    result = _inject_cover(tmp_path, dry_run=False)

    assert result is False
    assert not (tmp_path / COVER_CHAPTER_DIR).exists()


def test_inject_cover_dry_run(tmp_path: Path):
    cover = tmp_path / COVER_FILENAME
    cover.write_bytes(b"webp_data")

    result = _inject_cover(tmp_path, dry_run=True)

    assert result is True
    assert not (tmp_path / COVER_CHAPTER_DIR).exists()


def test_cleanup_removes_chapter_000(tmp_path: Path):
    chapter_dir = tmp_path / COVER_CHAPTER_DIR
    chapter_dir.mkdir()
    (chapter_dir / COVER_FILENAME).write_bytes(b"x")

    _cleanup_cover_chapter(tmp_path)

    assert not chapter_dir.exists()


def test_cleanup_noop_when_no_chapter_000(tmp_path: Path):
    _cleanup_cover_chapter(tmp_path)
    assert not (tmp_path / COVER_CHAPTER_DIR).exists()


def test_convert_volume_injects_and_cleans_up(tmp_path: Path):
    vol_dir = tmp_path / "volume"
    vol_dir.mkdir()
    cover = vol_dir / COVER_FILENAME
    cover.write_bytes(b"webp_data")
    out = tmp_path / "out.kepub.epub"

    with patch("convertor.kcc_adapter.KCCAdapter.run_module", return_value=0):
        convert_volume(vol_dir, out, dry_run=False)

    assert not (vol_dir / COVER_CHAPTER_DIR).exists()
    assert cover.exists()


def test_convert_volume_no_cover_no_chapter_000(tmp_path: Path):
    vol_dir = tmp_path / "volume"
    vol_dir.mkdir()
    out = tmp_path / "out.kepub.epub"

    with patch("convertor.kcc_adapter.KCCAdapter.run_module", return_value=0):
        convert_volume(vol_dir, out, dry_run=False)

    assert not (vol_dir / COVER_CHAPTER_DIR).exists()


def test_convert_volume_dry_run_no_cleanup(tmp_path: Path):
    vol_dir = tmp_path / "volume"
    vol_dir.mkdir()
    cover = vol_dir / COVER_FILENAME
    cover.write_bytes(b"webp_data")
    out = tmp_path / "out.kepub.epub"

    with patch("convertor.kcc_adapter.KCCAdapter.run_module", return_value=0):
        convert_volume(vol_dir, out, dry_run=True)

    assert not (vol_dir / COVER_CHAPTER_DIR).exists()
