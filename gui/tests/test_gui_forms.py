from __future__ import annotations

import doctest
import json
from pathlib import Path

import pytest
import yaml
from manga_gui import forms
from manga_gui.forms import (
    BatchRow,
    StepStatus,
    apply_series_fields,
    batch_rows_from_spec,
    batch_rows_from_text,
    batch_rows_to_spec,
    batch_rows_to_text,
    chapter_titles,
    cover_rows,
    effective_batch_file,
    effective_kcc,
    from_tri_state,
    packer_json_covers,
    parse_metadata_text,
    read_batch_file,
    reading_direction,
    save_metadata_text,
    save_packer_json_text,
    scan_rows,
    series_fields,
    set_packer_json_covers,
    set_packer_json_kind,
    step_status,
    switch_volume_mode,
    tri_state,
    volume_mode,
    volume_rows,
    write_batch_file,
)
from manga_gui.models import KCCOptions, Kind, PackerOptions, Project
from manga_gui.runner import StepResult
from manga_gui.scan import scan_library

from convertor.kcc_adapter import PRESETS
from packer.cli import parse_batch_file, parse_batch_spec


def test_doctests() -> None:
    assert doctest.testmod(forms).failed == 0


# -- batch table ----------------------------------------------------------


def test_batch_file_round_trip_with_packer_parser(tmp_path: Path) -> None:
    rows = [BatchRow(1, "1..12"), BatchRow(2, "13..26"), BatchRow(10, "27")]
    path = tmp_path / "vols.csv"
    write_batch_file(path, rows)
    assert path.read_text() == "v01,1..12\nv02,13..26\nv10,27\n"
    assert parse_batch_file(str(path)) == [
        (1, list(range(1, 13))),
        (2, list(range(13, 27))),
        (10, [27]),
    ]
    assert read_batch_file(path) == rows


def test_batch_rows_from_text_real_style() -> None:
    text = "# comment\n\nv1,1..12\n2 , 13..26\n"
    assert batch_rows_from_text(text) == [BatchRow(1, "1..12"), BatchRow(2, "13..26")]


@pytest.mark.parametrize("text", ["v01", "x,1..2"])
def test_batch_rows_from_text_invalid(text: str) -> None:
    with pytest.raises(ValueError):
        batch_rows_from_text(text)


def test_batch_rows_to_text_rejects_invalid_rows() -> None:
    with pytest.raises(ValueError, match="invalid range"):
        batch_rows_to_text([BatchRow(1, "5..2")])
    with pytest.raises(ValueError, match="more than once"):
        batch_rows_to_text([BatchRow(1, "1"), BatchRow(1, "2")])
    with pytest.raises(ValueError, match="not allowed"):
        batch_rows_to_text([BatchRow(1, "1,3")])


def test_read_batch_file_missing(tmp_path: Path) -> None:
    assert read_batch_file(tmp_path / "nope.csv") == []


def test_batch_spec_round_trip() -> None:
    rows = batch_rows_from_spec("v01:1..3-v2:4,6")
    assert rows == [BatchRow(1, "1..3"), BatchRow(2, "4,6")]
    spec = batch_rows_to_spec(rows)
    assert spec == "v01:1..3-v02:4,6"
    assert parse_batch_spec(spec) == [(1, [1, 2, 3]), (2, [4, 6])]
    assert batch_rows_from_spec(None) == []
    with pytest.raises(ValueError):
        batch_rows_from_spec("vol1")


def test_effective_batch_file(tmp_path: Path, write_json) -> None:
    p = Project(name="x", source=tmp_path)
    assert effective_batch_file(p) == tmp_path / ".batch"
    write_json(tmp_path / "packer.json", {"batch_file": "vols.csv"})
    assert effective_batch_file(p) == tmp_path / "vols.csv"
    p.packer.batch_file = tmp_path / "other.csv"
    assert effective_batch_file(p) == tmp_path / "other.csv"


# -- volume mode -----------------------------------------------------------


def test_volume_mode_switch_keeps_stash() -> None:
    opts = PackerOptions(batch="v01:1..3")
    stash: dict = {}
    assert volume_mode(opts) == "spec"
    switch_volume_mode(opts, "single", stash)
    assert opts.batch is None and stash == {"batch": "v01:1..3"}
    opts.volume, opts.chapter_range = 2, "1..4"
    assert volume_mode(opts) == "single"
    switch_volume_mode(opts, "spec", stash)
    assert opts.batch == "v01:1..3"
    assert opts.volume is None and opts.chapter_range is None
    switch_volume_mode(opts, "single", stash)
    assert (opts.volume, opts.chapter_range, opts.batch) == (2, "1..4", None)
    switch_volume_mode(opts, "file", stash)
    assert volume_mode(opts) == "file"


# -- packer.json -----------------------------------------------------------


def test_save_packer_json_text_validates(tmp_path: Path) -> None:
    path = tmp_path / "packer.json"
    path.write_text('{"serie": "old"}')
    with pytest.raises(ValueError):
        save_packer_json_text(path, "{not json")
    with pytest.raises(ValueError, match="kind"):
        save_packer_json_text(path, '{"kind": "novel"}')
    assert path.read_text() == '{"serie": "old"}'
    assert not list(tmp_path.glob(".*.tmp"))
    assert save_packer_json_text(path, '{"serie": "new"}') == {"serie": "new"}
    assert json.loads(path.read_text()) == {"serie": "new"}


def test_set_packer_json_kind_preserves_keys(tmp_path: Path, write_json) -> None:
    path = tmp_path / "packer.json"
    assert set_packer_json_kind(path, Kind.COMIC) is False
    assert not path.exists()
    write_json(path, {"serie": "Saga", "covers": {"1": "c1.webp"}})
    assert set_packer_json_kind(path, Kind.COMIC) is True
    text = path.read_text()
    assert json.loads(text) == {
        "serie": "Saga",
        "covers": {"1": "c1.webp"},
        "kind": "comic",
    }
    assert text == json.dumps(json.loads(text), indent=2) + "\n"
    assert set_packer_json_kind(path, Kind.COMIC) is False


def test_covers_round_trip(tmp_path: Path, write_json) -> None:
    path = tmp_path / "packer.json"
    write_json(path, {"serie": "S", "covers": {"2": "c2.webp", "x": "bad"}})
    assert packer_json_covers(path) == {2: "c2.webp"}
    set_packer_json_covers(path, {10: "c10.webp", 2: "c2.webp", 3: "  "})
    data = json.loads(path.read_text())
    assert data == {"serie": "S", "covers": {"2": "c2.webp", "10": "c10.webp"}}
    set_packer_json_covers(path, {})
    assert json.loads(path.read_text()) == {"serie": "S"}
    assert packer_json_covers(tmp_path / "missing.json") == {}


def test_set_covers_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "packer.json"
    set_packer_json_covers(path, {1: "/abs/c.webp"})
    assert json.loads(path.read_text()) == {"covers": {"1": "/abs/c.webp"}}


def test_cover_rows(tmp_path: Path) -> None:
    (tmp_path / "c1.webp").write_bytes(b"x")
    rows = cover_rows(tmp_path / "packer.json", [1, 2], {1: "c1.webp", 5: "/n/a"})
    assert [(r.volume, r.raw, r.exists) for r in rows] == [
        (1, "c1.webp", True),
        (2, "", False),
        (5, "/n/a", False),
    ]
    assert rows[0].resolved == tmp_path / "c1.webp"
    assert rows[1].resolved is None


# -- KCC -------------------------------------------------------------------


@pytest.mark.parametrize("value", [None, True, False])
def test_tri_state_round_trip(value: bool | None) -> None:
    assert from_tri_state(tri_state(value)) is value


def test_effective_kcc_uses_presets() -> None:
    assert effective_kcc(Kind.MANGA, KCCOptions()) == PRESETS["manga"]
    comic = effective_kcc(Kind.COMIC, KCCOptions())
    assert comic == PRESETS["comic"]
    assert reading_direction(comic) == "Left-to-right (comic)"
    custom = effective_kcc(Kind.COMIC, KCCOptions(manga_style=True, rotation=0))
    assert custom.manga_style is True and custom.rotation == 0
    assert reading_direction(custom) == "Right-to-left (manga)"


# -- metadata --------------------------------------------------------------

_META = {
    "series": "Jujutsu Kaisen Modulo",
    "author": ["Gege Akutami", "Yuji Iwasaki"],
    "genre": ["Shonen", "Action"],
    "publisher": {"japanese": "Shueisha", "english": "Viz Media"},
    "volumes": [
        {
            "number": 1,
            "title": "Special Grade Incident",
            "english": {"isbn": "978-1", "release_date": "2026-01-05"},
        },
        {"number": 2, "title": "Dura"},
    ],
}


def test_series_fields_and_volume_rows() -> None:
    fields = series_fields(_META, "english")
    assert fields == {
        "series": "Jujutsu Kaisen Modulo",
        "author": "Gege Akutami, Yuji Iwasaki",
        "publisher": "Viz Media",
        "language": "",
        "kind": "",
        "genre": "Shonen, Action",
    }
    rows = volume_rows(_META, "english")
    assert rows[0].isbn == "978-1" and rows[0].release_date == "2026-01-05"
    assert rows[1].isbn == "" and rows[1].title == "Dura"


def test_apply_series_fields_only_changes_edited_keys() -> None:
    fields = series_fields(_META, "english")
    assert apply_series_fields(_META, fields, "english") == _META
    edited = {**fields, "kind": "comic", "publisher": "Viz", "genre": "A, B"}
    out = apply_series_fields(_META, edited, "english")
    assert out["kind"] == "comic"
    assert out["publisher"] == {"japanese": "Shueisha", "english": "Viz"}
    assert out["genre"] == ["A", "B"]
    assert out["author"] == _META["author"]
    assert list(out).index("kind") < list(out).index("volumes")
    cleared = apply_series_fields(_META, {**fields, "genre": ""}, "english")
    assert "genre" not in cleared


def test_save_metadata_text_validates(tmp_path: Path) -> None:
    path = tmp_path / "meta.yaml"
    with pytest.raises(ValueError, match="mapping"):
        save_metadata_text(path, "- a\n- b\n")
    with pytest.raises(ValueError, match="invalid YAML"):
        save_metadata_text(path, "a: [\n")
    with pytest.raises(ValueError, match="kind"):
        save_metadata_text(path, "kind: novel\n")
    assert not path.exists()
    text = "# keep me\nseries: S\nvolumes:\n- number: 1\n"
    assert save_metadata_text(path, text)["series"] == "S"
    assert path.read_text() == text


def test_parse_metadata_text() -> None:
    assert parse_metadata_text("") == {}
    assert parse_metadata_text(forms.dump_yaml(_META)) == _META
    with pytest.raises(ValueError):
        parse_metadata_text("[1]")


def test_chapter_titles_sources(tmp_path: Path, write_yaml) -> None:
    meta = tmp_path / "meta.yaml"
    assert chapter_titles({}, meta, None).source == "none"
    inline = chapter_titles(
        {"chapters": [{"number": 2, "title": "B"}, {"number": 1, "title": "A"}]},
        meta,
        None,
    )
    assert inline.titles == {1: "A", 2: "B"} and inline.source == "inline chapters"
    write_yaml(tmp_path / "ch.yaml", {"chapters": [{"number": 3, "title": "C"}]})
    from_file = chapter_titles({"chapters_file": "ch.yaml"}, meta, None)
    assert from_file.titles == {3: "C"} and from_file.error is None
    missing = chapter_titles({}, meta, tmp_path / "nope.yaml")
    assert missing.error is not None and "not found" in missing.error
    write_yaml(tmp_path / "bad.yaml", {"chapters": [{"number": "0-1", "title": "X"}]})
    bad = chapter_titles({"chapters_file": "bad.yaml"}, meta, None)
    assert bad.error is not None and bad.titles == {}


# -- scan / status ---------------------------------------------------------


def test_scan_rows_flags_duplicates(tmp_path: Path, make_library) -> None:
    src = make_library(tmp_path / "lib", ["A Chapter 1.cbz", "B Chapter 1.cbz"])
    rows = scan_rows(scan_library(Project(name="x", source=src)))
    assert [r["duplicate"] for r in rows] == [True, True]
    assert rows[0]["number"] == 1 and rows[0]["extra"] == ""


def test_step_status() -> None:
    ok = StepResult("packer", [], 0, 0.1)
    assert step_status(ok) is StepStatus.OK
    assert step_status(ok._replace(exit_code=2)) is StepStatus.FAILED
    assert step_status(ok._replace(cancelled=True)) is StepStatus.CANCELLED


def test_yaml_dump_keeps_unicode() -> None:
    assert "Pokémon" in forms.dump_yaml({"series": "Pokémon"})
    assert yaml.safe_load(forms.dump_yaml(_META)) == _META
