"""Tests for uncovered error paths in packer/core.py and packer/worker.py."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from packer.core import has_comicinfo
from packer.worker import _safe_extract, process_one

# ---------------------------------------------------------------------------
# core.py — has_comicinfo() with bad zip (lines 200-201)
# ---------------------------------------------------------------------------


def test_has_comicinfo_bad_zip(tmp_path: Path):
    bad = tmp_path / "bad.cbz"
    bad.write_bytes(b"not a zip file")
    assert has_comicinfo(bad) is False


def test_has_comicinfo_valid_with_comicinfo(tmp_path: Path):
    cbz = tmp_path / "good.cbz"
    with zipfile.ZipFile(cbz, "w") as z:
        z.writestr("ComicInfo.xml", "<ComicInfo/>")
        z.writestr("001.jpg", "img")
    assert has_comicinfo(cbz) is True


def test_has_comicinfo_valid_without_comicinfo(tmp_path: Path):
    cbz = tmp_path / "no_info.cbz"
    with zipfile.ZipFile(cbz, "w") as z:
        z.writestr("001.jpg", "img")
    assert has_comicinfo(cbz) is False


# ---------------------------------------------------------------------------
# worker.py — _safe_extract() path traversal (line 25)
# ---------------------------------------------------------------------------


def test_safe_extract_path_traversal_raises(tmp_path: Path):
    malicious = tmp_path / "malicious.cbz"
    with zipfile.ZipFile(malicious, "w") as z:
        # Add a member with a path-traversal name
        info = zipfile.ZipInfo("../../etc/passwd")
        z.writestr(info, "data")

    dest = tmp_path / "output"
    dest.mkdir()
    with zipfile.ZipFile(malicious, "r") as zf:
        with pytest.raises(ValueError, match="Path traversal"):
            _safe_extract(zf, dest)


def test_safe_extract_normal_succeeds(tmp_path: Path):
    normal = tmp_path / "normal.cbz"
    with zipfile.ZipFile(normal, "w") as z:
        z.writestr("001.jpg", "image data")

    dest = tmp_path / "output"
    dest.mkdir()
    with zipfile.ZipFile(normal, "r") as zf:
        _safe_extract(zf, dest)

    assert (dest / "001.jpg").exists()


# ---------------------------------------------------------------------------
# worker.py — process_one() with bad zip raises RuntimeError (lines 98-99)
# ---------------------------------------------------------------------------


def test_process_one_missing_comicinfo_raises(tmp_path: Path):
    """An archive without ComicInfo.xml causes process_one to raise RuntimeError."""
    from packer.config import Config

    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()

    cbz = src / "Chapter 001.cbz"
    with zipfile.ZipFile(cbz, "w") as z:
        z.writestr("001.jpg", "img")  # no ComicInfo.xml

    cfg = Config(
        path=str(src),
        dest=str(dest),
        serie="Manga",
        volume=1,
        chapter_range=[1],
        nb_worker=1,
        dry_run=False,
        verbose=False,
        force=False,
        chapter_pat=None,
        extra_pat=None,
        covers=None,
    )

    vol_dir = dest / "Manga v01"
    vol_dir.mkdir()

    with pytest.raises(RuntimeError, match="Missing ComicInfo.xml"):
        process_one("1", str(cbz), cfg)


# ---------------------------------------------------------------------------
# worker.py — thread exception → PROCESSING_ERROR (lines 204-206)
# ---------------------------------------------------------------------------


def test_threaded_bad_zip_returns_processing_error(tmp_path: Path):
    """With nb_worker > 1, a bad zip causes PROCESSING_ERROR return code."""
    from packer.config import Config
    from packer.exit_codes import PROCESSING_ERROR
    from packer.worker import process_volume

    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()

    (src / "Chapter 001.cbz").write_bytes(b"not a zip")

    cfg = Config(
        path=str(src),
        dest=str(dest),
        serie="Manga",
        volume=1,
        chapter_range=[1],
        nb_worker=2,
        dry_run=False,
        verbose=False,
        force=False,
        chapter_pat=None,
        extra_pat=None,
        covers=None,
    )

    available = [str(src / "Chapter 001.cbz")]
    rc, _ = process_volume(1, [1], available, cfg)
    assert rc == PROCESSING_ERROR
