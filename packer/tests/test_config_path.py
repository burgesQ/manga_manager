"""Tests for the explicit ``--config`` packer.json path flag."""

import json
from pathlib import Path


def test_explicit_config_path_applies(tmp_path: Path, make_cbz, run_packer):
    """--config points at a packer.json outside --path and its keys apply."""
    src = tmp_path / "src"
    src.mkdir()
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "my_packer.json"
    cfg_file.write_text(json.dumps({"serie": "FromConfig", "pattern": "mangafire"}))

    make_cbz(src, "Chap 16.cbz")

    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--config",
            str(cfg_file),
            "--volume",
            "1",
            "--chapter-range",
            "16",
        ],
    )
    assert res.returncode == 0
    # serie + pattern came from the explicitly-specified config file
    assert (src / "FromConfig v01").exists()


def test_explicit_missing_config_errors(tmp_path: Path, run_packer):
    """An explicit --config path that does not exist is a hard error."""
    src = tmp_path / "src"
    src.mkdir()
    missing = tmp_path / "nope.json"

    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--config",
            str(missing),
            "--serie",
            "X",
            "--volume",
            "1",
            "--chapter-range",
            "1",
        ],
    )
    assert res.returncode == 2
    out = res.stderr or res.stdout
    assert "Config file not found" in out
    assert str(missing) in out


def test_missing_default_config_is_optional(tmp_path: Path, make_cbz, run_packer):
    """Without --config and no packer.json in --path, packing still works."""
    src = tmp_path / "src"
    src.mkdir()
    make_cbz(src, "Chapter 1.cbz")

    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "NoConfig",
            "--volume",
            "1",
            "--chapter-range",
            "1",
        ],
    )
    assert res.returncode == 0
    assert (src / "NoConfig v01").exists()


def test_config_help_shows_default():
    """--help advertises the default expected config location."""
    from packer.cli import _build_parser

    help_text = _build_parser().format_help()
    assert "--config" in help_text
    assert "<--path>/packer.json" in help_text
