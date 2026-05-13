"""Tests for uncovered error paths in convertor/cli.py."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import convertor.cli


# ---------------------------------------------------------------------------
# lines 113-114: root does not exist → return 2
# ---------------------------------------------------------------------------


def test_nonexistent_root_returns_error(tmp_path: Path):
    rc = convertor.cli.main([str(tmp_path / "missing")])
    assert rc == 2


# ---------------------------------------------------------------------------
# lines 118-119: no volume directories found → warning, return 0
# ---------------------------------------------------------------------------


def test_empty_root_returns_success(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    rc = convertor.cli.main([str(root)])
    assert rc == 0


# ---------------------------------------------------------------------------
# lines 126-128: force_regen removes existing output before converting
# ---------------------------------------------------------------------------


def test_force_regen_removes_existing_output(tmp_path: Path, make_vol):
    root = tmp_path / "root"
    root.mkdir()
    vol = make_vol(root)
    out = vol.with_name(vol.name + ".kepub.epub")
    out.write_text("old")

    with patch("convertor.cli.convert_volume") as mock_cv:
        mock_cv.return_value = out
        rc = convertor.cli.main([str(root), "--force-regen"])

    assert rc == 0
    mock_cv.assert_called_once()


# ---------------------------------------------------------------------------
# lines 129-130: OSError on unlink during force_regen → warning, continues
# ---------------------------------------------------------------------------


def test_force_regen_oserror_on_unlink_continues(tmp_path: Path, make_vol, capsys):
    root = tmp_path / "root"
    root.mkdir()
    vol = make_vol(root)
    out = vol.with_name(vol.name + ".kepub.epub")
    out.write_text("old")

    original_unlink = Path.unlink

    def raising_unlink(self, missing_ok=False):
        if self == out:
            raise OSError("permission denied")
        return original_unlink(self, missing_ok=missing_ok)

    with patch.object(Path, "unlink", raising_unlink):
        with patch("convertor.cli.convert_volume") as mock_cv:
            mock_cv.return_value = out
            rc = convertor.cli.main([str(root), "--force-regen"])

    assert rc == 0
    assert "could not remove" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# lines 140-141: RuntimeError from convert_volume → logged, loop continues
# ---------------------------------------------------------------------------


def test_runtime_error_from_conversion_is_logged(tmp_path: Path, make_vol, capsys):
    root = tmp_path / "root"
    root.mkdir()
    make_vol(root, "Series v01")
    make_vol(root, "Series v02")

    call_count = 0

    def fail_first(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("KCC crashed")

    with patch("convertor.cli.convert_volume", side_effect=fail_first):
        rc = convertor.cli.main([str(root)])

    assert rc == 0
    assert call_count == 2
    assert "conversion failed" in capsys.readouterr().err


def test_called_process_error_from_conversion_is_logged(tmp_path: Path, make_vol, capsys):
    root = tmp_path / "root"
    root.mkdir()
    make_vol(root)

    def raise_cpe(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "kcc-c2e")

    with patch("convertor.cli.convert_volume", side_effect=raise_cpe):
        rc = convertor.cli.main([str(root)])

    assert rc == 0
    assert "conversion failed" in capsys.readouterr().err


def test_oserror_from_conversion_is_logged(tmp_path: Path, make_vol, capsys):
    root = tmp_path / "root"
    root.mkdir()
    make_vol(root)

    with patch("convertor.cli.convert_volume", side_effect=OSError("disk full")):
        rc = convertor.cli.main([str(root)])

    assert rc == 0
    assert "conversion failed" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# lines 132-133: existing output without --force-regen → skip + continue
# ---------------------------------------------------------------------------


def test_existing_output_without_force_regen_is_skipped(tmp_path: Path, make_vol, capsys):
    root = tmp_path / "root"
    root.mkdir()
    vol = make_vol(root)
    out = vol.with_name(vol.name + ".kepub.epub")
    out.write_text("existing")

    with patch("convertor.cli.convert_volume") as mock_cv:
        rc = convertor.cli.main([str(root)])

    assert rc == 0
    mock_cv.assert_not_called()
    assert "skipping existing output" in capsys.readouterr().err
