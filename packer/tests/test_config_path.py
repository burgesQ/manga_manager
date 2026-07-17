"""Tests for the explicit ``--config`` packer.json path flag."""

import argparse
import json
import os
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


# --- path resolution (~, $VAR, absolute, relative) -------------------------


def test_resolve_config_path_expands_home():
    from packer.cli import _resolve_config_path

    got = _resolve_config_path("~/cover.webp", "/base")
    assert got == os.path.join(os.path.expanduser("~"), "cover.webp")
    assert "~" not in got


def test_resolve_config_path_expands_env(monkeypatch):
    from packer.cli import _resolve_config_path

    monkeypatch.setenv("MYDIR", "/env/dir")
    assert _resolve_config_path("$MYDIR/x.csv", "/base") == "/env/dir/x.csv"


def test_resolve_config_path_absolute_untouched():
    from packer.cli import _resolve_config_path

    assert _resolve_config_path("/abs/x.csv", "/base") == "/abs/x.csv"


def test_resolve_config_path_relative_against_base():
    from packer.cli import _resolve_config_path

    assert _resolve_config_path("./sub/x.csv", "/base") == "/base/sub/x.csv"


def test_apply_path_config_resolves_batch_and_covers(tmp_path: Path):
    """batch_file and cover paths resolve against the config dir, with ~ expanded."""
    from packer.cli import _apply_path_config

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "vols.csv").write_text("v01,1..3\n")
    cfg_file = cfg_dir / "packer.json"
    cfg_file.write_text(
        json.dumps(
            {
                "batch_file": "./vols.csv",  # relative -> resolved vs config dir
                "covers": {"1": "~/c1.webp"},  # ~ -> expanded to $HOME
            }
        )
    )

    args = argparse.Namespace(
        path=str(tmp_path / "src"),  # deliberately NOT where the config lives
        config=str(cfg_file),
        pattern="default",
        chapter_regex=None,
        extra_regex=None,
        nb_worker=1,
        batch_file=None,
        serie=None,
    )
    covers = _apply_path_config(args)

    # relative batch_file resolved against the config dir, NOT --path
    assert args.batch_file == str(cfg_dir / "vols.csv")
    # ~ in the cover path is expanded, not prefixed with --path
    assert covers is not None
    assert covers[0].cover_path == os.path.join(os.path.expanduser("~"), "c1.webp")
