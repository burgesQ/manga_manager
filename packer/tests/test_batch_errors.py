"""Actionable error messages for invalid batch specs / batch files."""

from __future__ import annotations

from pathlib import Path

import pytest

from packer.cli import main, parse_batch_file, parse_batch_spec
from packer.core import parse_range
from packer.exit_codes import CLI_ERROR

SKIP_HINT = "comment the line out with '#' to skip it"


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# --- parse_range -----------------------------------------------------------


def test_parse_range_rejects_ranged_chapter_id():
    with pytest.raises(ValueError, match="chapter numbers must be integers, got '0-1'"):
        parse_range("0-1..0-4")


# --- parse_batch_file ------------------------------------------------------


def test_batch_file_invalid_range_names_file_line_and_range(tmp_path):
    batch = _write(tmp_path / "vols_jjk.csv", "v0,0-1..0-4\nv1,1..7\n")
    with pytest.raises(ValueError) as exc:
        parse_batch_file(str(batch))
    assert str(exc.value) == (
        "vols_jjk.csv:1: invalid chapter range '0-1..0-4' in 'v0,0-1..0-4' "
        f"(chapter numbers must be integers, got '0-1'; {SKIP_HINT})"
    )


def test_batch_file_line_number_counts_comments_and_blanks(tmp_path):
    batch = _write(tmp_path / "vols.csv", "# header\n\nv01,1..3\nv02,4..x\n")
    with pytest.raises(ValueError, match=r"^vols\.csv:4: invalid chapter range "):
        parse_batch_file(str(batch))


def test_batch_file_reversed_range_reports_reason(tmp_path):
    batch = _write(tmp_path / "vols.csv", "v01,5..3\n")
    with pytest.raises(ValueError) as exc:
        parse_batch_file(str(batch))
    msg = str(exc.value)
    assert msg.startswith("vols.csv:1: invalid chapter range '5..3' in 'v01,5..3'")
    assert "end < start" in msg
    assert SKIP_HINT in msg


def test_batch_file_invalid_volume_token(tmp_path):
    batch = _write(tmp_path / "vols.csv", "v01,1..3\nvol2,4..6\n")
    with pytest.raises(ValueError) as exc:
        parse_batch_file(str(batch))
    assert str(exc.value) == (
        "vols.csv:2: invalid volume 'vol2' in 'vol2,4..6' "
        f"(expected 'vNN' or 'NN'; {SKIP_HINT})"
    )


def test_batch_file_line_without_range(tmp_path):
    batch = _write(tmp_path / "vols.csv", "v01\n")
    with pytest.raises(ValueError) as exc:
        parse_batch_file(str(batch))
    msg = str(exc.value)
    assert msg.startswith("vols.csv:1: invalid batch line 'v01'")
    assert SKIP_HINT in msg


def test_batch_file_commented_ranged_line_is_skipped(tmp_path):
    batch = _write(tmp_path / "vols_jjk.csv", "#v0,0-1..0-4\nv1,1..3\n02,4..5\n")
    assert parse_batch_file(str(batch)) == [(1, [1, 2, 3]), (2, [4, 5])]


# --- parse_batch_spec ------------------------------------------------------


def test_batch_spec_invalid_range_names_item():
    with pytest.raises(ValueError) as exc:
        parse_batch_spec("v01:1..3-v02:4..x")
    assert str(exc.value) == (
        "invalid chapter range '4..x' in batch spec item 'v02:4..x' "
        "(chapter numbers must be integers, got 'x')"
    )


def test_batch_spec_invalid_item_names_item_and_spec():
    with pytest.raises(ValueError) as exc:
        parse_batch_spec("v01:1..3-oops")
    msg = str(exc.value)
    assert msg.startswith("invalid batch spec item 'oops' in 'v01:1..3-oops'")
    assert "'v01:1..3-v02:4..6'" in msg


def test_batch_spec_ranged_ids_explain_dash_separator():
    # '-' splits items, so 'v0:0-1..0-4' yields the stray item '1..0'
    with pytest.raises(ValueError) as exc:
        parse_batch_spec("v0:0-1..0-4")
    msg = str(exc.value)
    assert "invalid batch spec item '1..0' in 'v0:0-1..0-4'" in msg
    assert "ranged chapter ids like '0-1' are not supported" in msg


# --- main() ----------------------------------------------------------------


def test_main_bad_batch_file_returns_cli_error(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    batch = _write(src / "bad.csv", "v1,1..3\nv0,0-1..0-4\n")
    rc = main(["--path", str(src), "--serie", "JJK", "--batch-file", str(batch)])
    assert rc == CLI_ERROR
    err = capsys.readouterr().err
    assert "bad.csv:2: invalid chapter range '0-1..0-4' in 'v0,0-1..0-4'" in err
    assert SKIP_HINT in err


def test_main_bad_batch_spec_returns_cli_error(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    rc = main(["--path", str(src), "--serie", "JJK", "--batch", "v01:1..x"])
    assert rc == CLI_ERROR
    err = capsys.readouterr().err
    assert "invalid chapter range '1..x' in batch spec item 'v01:1..x'" in err


def test_main_bad_chapter_range_returns_cli_error(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    rc = main(
        [
            "--path",
            str(src),
            "--serie",
            "JJK",
            "--volume",
            "0",
            "--chapter-range",
            "0-1..0-4",
        ]
    )
    assert rc == CLI_ERROR
    err = capsys.readouterr().err
    assert (
        "invalid --chapter-range '0-1..0-4' "
        "(chapter numbers must be integers, got '0-1')" in err
    )


def test_batch_file_range_with_commas_keeps_every_chapter(tmp_path):
    batch = tmp_path / "vols.csv"
    batch.write_text("v01,1,3,5..8\nv02, 9..10 \n")
    assert parse_batch_file(batch) == [(1, [1, 3, 5, 6, 7, 8]), (2, [9, 10])]
