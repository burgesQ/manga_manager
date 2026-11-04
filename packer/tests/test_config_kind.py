"""Tests for the optional ``kind`` key in ``packer.json`` (roadmap item K2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packer.cli import VALID_KINDS, load_config_file, main
from packer.exit_codes import CLI_ERROR, SUCCESS


def _write_cfg(src: Path, cfg: dict) -> Path:
    path = src / "packer.json"
    path.write_text(json.dumps(cfg))
    return path


def _argv(src: Path) -> list[str]:
    return ["--path", str(src), "--volume", "1", "--chapter-range", "1"]


@pytest.mark.parametrize("kind", VALID_KINDS)
def test_load_config_file_accepts_valid_kind(tmp_path: Path, kind: str):
    cfg_path = _write_cfg(tmp_path, {"serie": "Saga", "kind": kind})
    assert load_config_file(str(cfg_path)) == {"serie": "Saga", "kind": kind}


@pytest.mark.parametrize("bad", ["webtoon", "Comic", "", 1, None])
def test_load_config_file_rejects_invalid_kind(tmp_path: Path, bad: object):
    cfg_path = _write_cfg(tmp_path, {"kind": bad})
    with pytest.raises(ValueError, match="kind must be one of manga, comic"):
        load_config_file(str(cfg_path))


def test_load_config_file_without_kind_is_unchanged(tmp_path: Path):
    cfg_path = _write_cfg(tmp_path, {"serie": "Berserk"})
    assert "kind" not in load_config_file(str(cfg_path))


def test_main_with_comic_kind_succeeds(tmp_path: Path, make_cbz, capsys):
    src = tmp_path / "src"
    src.mkdir()
    _write_cfg(src, {"serie": "Saga", "kind": "comic"})
    make_cbz(src, "Chapter 1.cbz")

    rc = main([*_argv(src), "--verbose"])

    assert rc == SUCCESS
    assert (src / "Saga v01" / "Chapter 1.cbz").exists()
    assert "packer.json kind: comic" in capsys.readouterr().err


def test_main_with_invalid_kind_is_cli_error(tmp_path: Path, make_cbz, capsys):
    src = tmp_path / "src"
    src.mkdir()
    cfg_path = _write_cfg(src, {"serie": "Saga", "kind": "webtoon"})
    make_cbz(src, "Chapter 1.cbz")

    rc = main(_argv(src))

    assert rc == CLI_ERROR
    err = capsys.readouterr().err
    assert "Invalid packer.json" in err
    assert str(cfg_path) in err
    assert "'webtoon'" in err
    # Nothing was packed.
    assert not (src / "Saga v01").exists()


def test_main_without_kind_is_unaffected(tmp_path: Path, make_cbz, capsys):
    src = tmp_path / "src"
    src.mkdir()
    _write_cfg(src, {"serie": "Berserk"})
    make_cbz(src, "Chapter 1.cbz")

    rc = main([*_argv(src), "--verbose"])

    assert rc == SUCCESS
    assert (src / "Berserk v01" / "Chapter 1.cbz").exists()
    assert "packer.json kind" not in capsys.readouterr().err
