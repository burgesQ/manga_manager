"""Tests for packer/cli.py main() — direct import for coverage instrumentation."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from packer.cli import main
from packer.exit_codes import CLI_ERROR, SUCCESS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cbz(path: Path, name: str, *, with_comicinfo: bool = True) -> Path:
    p = path / name
    with zipfile.ZipFile(p, "w") as z:
        if with_comicinfo:
            z.writestr("ComicInfo.xml", "<ComicInfo></ComicInfo>")
        z.writestr("001.jpg", "img")
    return p


def _args(
    src: Path, extra: list[str] | None = None, *, serie: str = "Manga"
) -> list[str]:
    base = ["--path", str(src), "--serie", serie]
    return base + (extra or [])


# ---------------------------------------------------------------------------
# Validation errors — no cbz files required
# ---------------------------------------------------------------------------


def test_batch_and_volume_mutually_exclusive(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    rc = main(_args(src, ["--batch", "v01:1..3", "--volume", "1"]))
    assert rc == CLI_ERROR


def test_missing_volume_and_range(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    rc = main(_args(src))
    assert rc == CLI_ERROR


def test_missing_serie(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    rc = main(["--path", str(src), "--volume", "1", "--chapter-range", "1"])
    assert rc == CLI_ERROR


def test_invalid_chapter_regex(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    rc = main(
        _args(
            src,
            ["--volume", "1", "--chapter-range", "1", "--chapter-regex", r"([unclosed"],
        )
    )
    assert rc == CLI_ERROR


def test_invalid_packer_json(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "packer.json").write_text("{ bad json }")
    rc = main(_args(src, ["--volume", "1", "--chapter-range", "1"]))
    assert rc == CLI_ERROR


def test_invalid_batch_spec(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    rc = main(_args(src, ["--batch", "notavalidspec"]))
    assert rc == CLI_ERROR


def test_batch_file_nonexistent(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    rc = main(_args(src, ["--batch-file", str(tmp_path / "missing.batch")]))
    assert rc == CLI_ERROR


# ---------------------------------------------------------------------------
# .batch auto-discovery (lines 346-348)
# ---------------------------------------------------------------------------


def test_auto_discover_batch_file(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    _make_cbz(src, "Ch.001.cbz")
    _make_cbz(src, "Ch.002.cbz")
    (src / ".batch").write_text("v01,1..2\n")
    rc = main(["--path", str(src), "--serie", "Manga"])
    assert rc == SUCCESS


# ---------------------------------------------------------------------------
# packer.json config merging (lines 294-312)
# ---------------------------------------------------------------------------


def test_packer_json_provides_serie(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    _make_cbz(src, "Ch.001.cbz")
    (src / "packer.json").write_text(json.dumps({"serie": "JsonManga"}))
    rc = main(["--path", str(src), "--volume", "1", "--chapter-range", "1"])
    assert rc == SUCCESS
    assert (src / "JsonManga v01").exists()


def test_packer_json_provides_pattern(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    _make_cbz(src, "Ch.001.cbz")
    (src / "packer.json").write_text(json.dumps({"pattern": "mangadex"}))
    rc = main(_args(src, ["--volume", "1", "--chapter-range", "1"]))
    assert rc == SUCCESS


def test_packer_json_provides_batch_file(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    _make_cbz(src, "Ch.001.cbz")
    batch = src / "my.batch"
    batch.write_text("v01,1\n")
    (src / "packer.json").write_text(
        json.dumps({"serie": "M", "batch_file": "my.batch"})
    )
    rc = main(["--path", str(src)])
    assert rc == SUCCESS


def test_cli_serie_overrides_packer_json(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    _make_cbz(src, "Ch.001.cbz")
    (src / "packer.json").write_text(json.dumps({"serie": "FromJson"}))
    rc = main(
        [
            "--path",
            str(src),
            "--serie",
            "FromCLI",
            "--volume",
            "1",
            "--chapter-range",
            "1",
        ]
    )
    assert rc == SUCCESS
    assert (src / "FromCLI v01").exists()
    assert not (src / "FromJson v01").exists()


def test_packer_json_provides_nb_worker(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    _make_cbz(src, "Ch.001.cbz")
    (src / "packer.json").write_text(json.dumps({"nb_worker": 2}))
    rc = main(_args(src, ["--volume", "1", "--chapter-range", "1"]))
    assert rc == SUCCESS


# ---------------------------------------------------------------------------
# --batch valid spec (lines 397-427)
# ---------------------------------------------------------------------------


def test_batch_spec_two_volumes(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    _make_cbz(src, "Ch.001.cbz")
    _make_cbz(src, "Ch.002.cbz")
    rc = main(_args(src, ["--batch", "v01:1-v02:2"]))
    assert rc == SUCCESS
    assert (src / "Manga v01").exists()
    assert (src / "Manga v02").exists()


# ---------------------------------------------------------------------------
# --batch-file valid (lines 403-408)
# ---------------------------------------------------------------------------


def test_batch_file_valid(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    _make_cbz(src, "Ch.001.cbz")
    _make_cbz(src, "Ch.002.cbz")
    batch = tmp_path / "my.batch"
    batch.write_text("v01,1\nv02,2\n")
    rc = main(_args(src, ["--batch-file", str(batch)]))
    assert rc == SUCCESS
    assert (src / "Manga v01").exists()
    assert (src / "Manga v02").exists()


# ---------------------------------------------------------------------------
# Named patterns (lines 369-371)
# ---------------------------------------------------------------------------


def test_pattern_mangafire(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    _make_cbz(src, "Chap 1.cbz")
    rc = main(
        _args(src, ["--volume", "1", "--chapter-range", "1", "--pattern", "mangafire"])
    )
    assert rc == SUCCESS


def test_pattern_animeSama(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    _make_cbz(src, "Chapitre 1.cbz")
    rc = main(
        _args(src, ["--volume", "1", "--chapter-range", "1", "--pattern", "animeSama"])
    )
    assert rc == SUCCESS


# ---------------------------------------------------------------------------
# Covers from packer.json (lines 316-336)
# ---------------------------------------------------------------------------


def test_packer_json_covers_missing_path_warns(tmp_path: Path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    _make_cbz(src, "Ch.001.cbz")
    config = {"serie": "Manga", "covers": {"1": "/nonexistent/cover.webp"}}
    (src / "packer.json").write_text(json.dumps(config))
    rc = main(["--path", str(src), "--volume", "1", "--chapter-range", "1"])
    assert rc == SUCCESS
    assert "not found" in capsys.readouterr().err


def test_packer_json_covers_invalid_type_skipped(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    _make_cbz(src, "Ch.001.cbz")
    config = {"serie": "Manga", "covers": "not-a-dict"}
    (src / "packer.json").write_text(json.dumps(config))
    rc = main(["--path", str(src), "--volume", "1", "--chapter-range", "1"])
    assert rc == SUCCESS
