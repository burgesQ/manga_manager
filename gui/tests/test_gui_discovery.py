"""Unit tests of manga_gui.discovery (series folders, metadata groups, import)."""

from __future__ import annotations

import doctest
import json
from pathlib import Path

import pytest
from manga_gui import discovery
from manga_gui.discovery import (
    ImportCandidate,
    MetadataGroup,
    apply_import,
    build_project,
    candidate_for_source,
    find_metadata_groups,
    find_series_dirs,
    format_plan,
    plan_import,
)
from manga_gui.models import Kind, Project
from manga_gui.store import Store


def test_doctests() -> None:
    assert doctest.testmod(discovery).failed == 0


def _by_label(cands: list[ImportCandidate]) -> dict[str | None, ImportCandidate]:
    return {c.label: c for c in cands}


# -- series folders ------------------------------------------------------------


def test_find_series_dirs(fake_shelf) -> None:
    found = find_series_dirs(fake_shelf.root)
    assert [s.label for s in found] == [
        "EN/Berserk",
        "EN/FmA",
        "EN/JJK",
        "EN/JJKM",
        "EN/Mashle",
        "EN/Zetman",
        "FR/Boruto",
        "FR/BorutoBlueVortex",
        "FR/Shangri-La Frontier",
    ]  # no NickelMenu (git repo), .Trash (hidden), files
    by = {s.label: s for s in found}
    assert by["EN/Berserk"].serie_names == ("Berserk",)
    assert by["EN/Berserk"].volume_count == 2 and by["EN/Berserk"].lang == "EN"
    assert by["EN/JJK"].serie_names == () and by["EN/JJK"].cbz_count == 1
    assert by["EN/Mashle"].packer_json is not None
    assert by["EN/Mashle"].serie_names == ("Mashle",)  # invalid json: volumes only
    assert by["FR/BorutoBlueVortex"].serie_names == (
        "Boruto: Two Blue Vortex",
        "Boruto Two Blue Vortex",
    )


def test_find_series_dirs_depth_and_root(tmp_path: Path) -> None:
    deep = tmp_path / "a" / "b" / "Saga"
    (deep / "covers").mkdir(parents=True)
    assert find_series_dirs(tmp_path) == []
    assert [s.label for s in find_series_dirs(tmp_path, max_depth=3)] == ["a/b/Saga"]
    # the root itself is a series folder
    (tmp_path / "Saga v01").mkdir()
    only = find_series_dirs(tmp_path)
    assert [(s.path, s.lang) for s in only] == [(tmp_path, None)]
    assert find_series_dirs(tmp_path / "missing") == []


# -- metadata groups -------------------------------------------------------------


def test_find_metadata_groups(fake_shelf) -> None:
    groups = {g.key: g for g in find_metadata_groups(fake_shelf.meta)}
    assert sorted(groups) == [
        "boruto",
        "boruto_bv",
        "fma",
        "jjk",
        "jjkm",
        "mashle",
        "shangri",
        "vinland",
        "zetman",
    ]  # no "chapters_jjk", "packer_fma", "vols_fma" or "notes" keys
    meta = fake_shelf.meta
    assert groups["jjk"] == MetadataGroup(
        "jjk",
        packer_json=meta / "packer_jjk.json",
        metadata_yaml=meta / "jjk.yaml",
        chapters_yaml=meta / "chapters_jjk.yaml",
        batch_csv=meta / "vols_jjk.csv",
    )
    assert groups["boruto"].files == [meta / "boruto.yaml"]
    assert find_metadata_groups(meta / "missing") == []


# -- matching / plan -------------------------------------------------------------


def test_plan_import_matches(fake_shelf, tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    cands = plan_import(fake_shelf.meta, fake_shelf.root, store)
    by = _by_label(cands)
    assert {label: c.key for label, c in by.items()} == {
        "EN/Berserk": None,
        "EN/FmA": "fma",
        "EN/JJK": "jjk",
        "EN/JJKM": "jjkm",
        "EN/Mashle": "mashle",
        "EN/Zetman": "zetman",
        "FR/Boruto": "boruto",
        "FR/BorutoBlueVortex": "boruto_bv",
        "FR/Shangri-La Frontier": "shangri",
        None: "vinland",
    }
    assert by["EN/FmA"].reason == "covers of packer_fma.json are in EN/FmA"
    assert by["EN/Mashle"].reason == "serie 'Mashle' matches EN/Mashle"
    assert by["FR/Boruto"].reason == "key 'boruto' matches folder 'Boruto'"
    assert "initials" in by["FR/BorutoBlueVortex"].reason
    assert "starts with 'shangri'" in by["FR/Shangri-La Frontier"].reason
    assert by["EN/Berserk"].reason == "series folder without metadata files"
    # importable first (by name), then the groups without folder
    assert [c.name for c in cands][-1] == "Vinland Saga"
    assert [c.importable for c in cands] == [True] * 9 + [False]


def test_plan_import_candidate_fields(fake_shelf, tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    meta, root = fake_shelf.meta, fake_shelf.root
    by = _by_label(plan_import(meta, root, store))

    fma = by["EN/FmA"]
    assert (fma.name, fma.slug, fma.kind) == (
        "Fullmetal Alchemist",
        "fullmetal-alchemist",
        Kind.MANGA,
    )
    assert fma.source == root / "EN" / "FmA"
    assert fma.packer_config == meta / "packer_fma.json"  # group's file first
    assert (fma.metadata, fma.chapters, fma.locale) == (
        meta / "fma.yaml",
        None,
        "english",
    )
    assert fma.issues == () and not fma.exists
    assert fma.files == ["packer_fma.json", "fma.yaml", "vols_fma.csv"]

    assert by["EN/JJK"].chapters is None  # jjk.yaml has chapters_file
    assert by["EN/JJKM"].chapters == meta / "chapters_jjkm.yaml"

    zetman = by["EN/Zetman"]
    assert zetman.kind is Kind.COMIC
    assert zetman.issues == ("metadata YAML volumes have no `english` block",)

    mashle = by["EN/Mashle"]
    assert mashle.packer_config == meta / "packer_mashle.json"  # both are invalid
    assert len(mashle.issues) == 1 and "Invalid packer.json" in mashle.issues[0]

    boruto, bv = by["FR/Boruto"], by["FR/BorutoBlueVortex"]
    assert (boruto.name, bv.name) == ("Boruto", "Boruto: Two Blue Vortex")
    assert boruto.packer_config == root / "FR" / "Boruto" / "packer.json"
    assert boruto.files == ["./packer.json", "boruto.yaml"]
    assert boruto.locale == "french"  # from the FR folder
    assert boruto.issues == ("metadata YAML volumes have no `french` block",)

    shangri = by["FR/Shangri-La Frontier"]
    assert shangri.name == "Shangri-La Frontier ~Kusoge Hunter~"  # yaml series
    assert shangri.packer_config is None and shangri.issues == ()

    berserk = by["EN/Berserk"]
    assert (berserk.name, berserk.packer_config, berserk.metadata) == (
        "Berserk",
        None,
        None,
    )

    vinland = by[None]
    assert (vinland.name, vinland.source, vinland.importable) == (
        "Vinland Saga",
        None,
        False,
    )
    assert vinland.status() == "no source"


def test_plan_import_group_packer_fallback(fake_shelf, tmp_path: Path) -> None:
    """An invalid group packer json falls back to a valid folder packer.json."""
    mashle = fake_shelf.root / "EN" / "Mashle" / "packer.json"
    mashle.write_text(json.dumps({"serie": "Mashle", "kind": "comic"}))
    by = _by_label(plan_import(fake_shelf.meta, fake_shelf.root, Store(tmp_path)))
    cand = by["EN/Mashle"]
    assert cand.packer_config == mashle and cand.kind is Kind.COMIC
    assert cand.issues[1] == "using EN/Mashle/packer.json instead"


def test_plan_import_locale_from_yaml(tmp_path: Path, write_yaml) -> None:
    root, meta = tmp_path / "lib", tmp_path / "meta"
    (root / "Saga" / "Saga v01").mkdir(parents=True)
    vols = [{"number": 1, "japanese": {}}, {"number": 2, "japanese": {}}]
    write_yaml(meta / "saga.yaml", {"series": "Saga", "volumes": vols})
    (cand,) = plan_import(meta, root, Store(tmp_path / "data"))
    assert (cand.reason, cand.locale, cand.issues) == (
        "serie 'Saga' matches Saga",
        "japanese",
        (),
    )


def test_plan_import_cover_paths_expand_user(
    tmp_path: Path, write_json, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "lib" / "XY" / "covers").mkdir(parents=True)
    write_json(
        tmp_path / "meta" / "packer_saga.json",
        {"serie": "Saga", "covers": {"1": "~/lib/XY/covers/1.webp"}},
    )
    (cand,) = plan_import(tmp_path / "meta", tmp_path / "lib", Store(tmp_path / "d"))
    assert cand.reason == "covers of packer_saga.json are in XY"


def test_plan_import_invalid_yaml_and_duplicate_slugs(
    tmp_path: Path, write_json
) -> None:
    root, meta = tmp_path / "lib", tmp_path / "meta"
    for lang in ("EN", "FR"):
        (root / lang / "Saga" / "Saga v01").mkdir(parents=True)
    meta.mkdir()
    (meta / "saga.yaml").write_text("series: [unclosed\n")
    cands = plan_import(meta, root, Store(tmp_path / "data"))
    assert [(c.name, c.slug, c.label) for c in cands] == [
        ("Saga", "saga", "EN/Saga"),
        ("Saga (FR)", "saga-fr", "FR/Saga"),
    ]
    assert cands[0].reason == "key 'saga' matches folder 'Saga'"
    assert "invalid metadata YAML (saga.yaml)" in cands[0].issues[0]


def test_plan_import_one_side_only(fake_shelf, tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    only_meta = plan_import(fake_shelf.meta, None, store)
    assert len(only_meta) == 9 and not any(c.importable for c in only_meta)
    only_lib = plan_import(None, fake_shelf.root, store)
    assert len(only_lib) == 9 and all(c.key is None for c in only_lib)
    assert plan_import(None, None, store) == []


def test_candidate_for_source(fake_shelf, tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    src = fake_shelf.root / "EN" / "Zetman"
    cand = candidate_for_source(src, fake_shelf.meta, fake_shelf.root, store)
    assert cand is not None and cand.key == "zetman"
    assert candidate_for_source(tmp_path, fake_shelf.meta, None, store) is None


# -- apply -----------------------------------------------------------------------


def test_apply_import(fake_shelf, tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    store.save_project(Project(name="Zetman", source=tmp_path / "old"))
    cands = plan_import(fake_shelf.meta, fake_shelf.root, store)
    assert _by_label(cands)["EN/Zetman"].exists
    before = {p: p.read_bytes() for p in fake_shelf.meta.iterdir()}

    report = apply_import(cands, store)
    assert len(report.created) == 8 and report.overwritten == []
    assert report.skipped == ["zetman"]
    assert report.failed == [("vinland-saga", "Vinland Saga: no source folder")]
    assert store.load_project("zetman").source == tmp_path / "old"

    project = store.load_project("jujutsu-kaisen-modulo")
    assert project.source == fake_shelf.root / "EN" / "JJKM"
    assert project.packer.config == fake_shelf.meta / "packer_jjkm.json"
    assert project.packer.serie is None and project.packer.pattern == "default"
    assert project.editor.metadata == fake_shelf.meta / "jjkm.yaml"
    assert project.editor.chapters == fake_shelf.meta / "chapters_jjkm.yaml"
    assert project.editor.locale == "english"
    # the user's files are untouched
    assert {p: p.read_bytes() for p in fake_shelf.meta.iterdir()} == before

    again = apply_import(cands, store, overwrite=True)
    assert len(again.overwritten) == 9 and again.created == []
    assert store.load_project("zetman").kind is Kind.COMIC


def test_apply_import_write_error(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    store.projects_dir.parent.mkdir(parents=True)
    store.projects_dir.write_text("not a dir")
    (tmp_path / "lib" / "Saga" / "covers").mkdir(parents=True)
    cands = plan_import(None, tmp_path / "lib", store)
    report = apply_import(cands, store)
    assert report.created == [] and report.failed[0][0] == "saga"
    assert report.summary() == "0 created, 0 overwritten, 0 skipped (exists), 1 failed"


def test_build_project_needs_a_source(fake_shelf, tmp_path: Path) -> None:
    orphan = plan_import(fake_shelf.meta, None, Store(tmp_path))[0]
    with pytest.raises(ValueError, match="no source folder"):
        build_project(orphan)


def test_format_plan(fake_shelf, tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    lines = format_plan(plan_import(fake_shelf.meta, fake_shelf.root, store))
    assert lines[0].split() == ["status", "name", "source", "files", "reason", "issues"]
    assert len(lines) == 11
    berserk = next(line for line in lines if "Berserk" in line)
    assert berserk.split()[:3] == ["new", "Berserk", "EN/Berserk"]
    assert lines[-1].startswith("no source  Vinland Saga")
    # columns are aligned: every "reason" cell starts at the same offset
    offsets = {
        line.index(c.reason)
        for line, c in zip(
            lines[1:], plan_import(fake_shelf.meta, fake_shelf.root, store), strict=True
        )
    }
    assert len(offsets) == 1
