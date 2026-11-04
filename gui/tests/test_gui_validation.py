from __future__ import annotations

from pathlib import Path

import pytest
from manga_gui.models import EditorOptions, KCCOptions, Kind, PackerOptions, Project
from manga_gui.validation import (
    compile_patterns,
    has_errors,
    resolve_batch_specs,
    resolve_packer_settings,
    validate_project,
)


@pytest.fixture
def good_project(tmp_path: Path, make_library, write_yaml) -> Project:
    src = make_library(tmp_path / "lib", ["Chapter 1.cbz", "Chapter 2.cbz"])
    meta = write_yaml(
        tmp_path / "meta.yaml",
        {"series": "Berserk", "volumes": [{"number": 1, "english": {"isbn": "1"}}]},
    )
    return Project(
        name="Berserk",
        source=src,
        packer=PackerOptions(serie="Berserk", volume=1, chapter_range="1..2"),
        editor=EditorOptions(metadata=meta),
    )


def _messages(issues, level: str | None = None) -> str:
    return "\n".join(
        f"{i.step}: {i.message}" for i in issues if level is None or i.level == level
    )


def test_good_project_has_no_issue(good_project: Project) -> None:
    assert validate_project(good_project) == []


def test_missing_source(tmp_path: Path) -> None:
    p = Project(
        name="x",
        source=tmp_path / "missing",
        packer=PackerOptions(serie="X", volume=1, chapter_range="1"),
        steps={"convertor": False, "editor": False},
    )
    issues = validate_project(p)
    assert has_errors(issues)
    assert "source folder not found" in _messages(issues, "error")


def test_no_step_enabled_warning(tmp_path: Path) -> None:
    p = Project(
        name="x",
        source=tmp_path,
        steps={"packer": False, "convertor": False, "editor": False},
    )
    issues = validate_project(p)
    assert [i.message for i in issues] == ["no step is enabled"]


def test_broken_packer_json(good_project: Project) -> None:
    (good_project.source / "packer.json").write_text("{broken")
    issues = validate_project(good_project)
    assert any(
        i.level == "error" and i.step == "packer" and "Invalid packer.json" in i.message
        for i in issues
    )


def test_explicit_missing_config_is_error(good_project: Project, tmp_path) -> None:
    good_project.packer.config = tmp_path / "nope.json"
    assert "Config file not found" in _messages(validate_project(good_project))


def test_serie_from_packer_json(good_project: Project, write_json) -> None:
    good_project.packer.serie = None
    assert "serie is required" in _messages(validate_project(good_project), "error")
    write_json(good_project.source / "packer.json", {"serie": "Berserk"})
    assert validate_project(good_project) == []


def test_bad_batch_spec(good_project: Project) -> None:
    good_project.packer = PackerOptions(serie="B", batch="x01:oops")
    assert "invalid batch" in _messages(validate_project(good_project), "error")


def test_batch_with_volume_is_error(good_project: Project) -> None:
    good_project.packer = PackerOptions(serie="B", batch="v01:1..2", volume=1)
    assert "cannot be combined" in _messages(validate_project(good_project), "error")


def test_bad_batch_file(good_project: Project, tmp_path: Path) -> None:
    bad = tmp_path / "bad.batch"
    bad.write_text("v01\n")
    good_project.packer = PackerOptions(serie="B", batch_file=bad)
    assert "invalid batch" in _messages(validate_project(good_project), "error")
    good_project.packer.batch_file = tmp_path / "missing.batch"
    assert "batch file not found" in _messages(validate_project(good_project))


def test_batch_file_from_packer_json(good_project: Project, write_json) -> None:
    (good_project.source / "cfg").mkdir()
    (good_project.source / "cfg" / "b.csv").write_text("v01,1..2\nv02,3\n")
    write_json(good_project.source / "packer.json", {"batch_file": "cfg/b.csv"})
    good_project.packer = PackerOptions(serie="B")
    settings = resolve_packer_settings(good_project)
    assert settings.batch_file == good_project.source / "cfg" / "b.csv"
    assert resolve_batch_specs(settings, good_project.source) == [
        (1, [1, 2]),
        (2, [3]),
    ]
    assert not has_errors(validate_project(good_project))


def test_packer_json_batch_overrides_volume_warning(
    good_project: Project, write_json
) -> None:
    (good_project.source / "b.csv").write_text("v01,1..2\n")
    write_json(good_project.source / "packer.json", {"batch": "b.csv"})
    issues = validate_project(good_project)
    assert "overrides volume/range" in _messages(issues, "warning")


def test_dot_batch_autodiscovery(good_project: Project) -> None:
    good_project.packer = PackerOptions(serie="B")
    assert "must be provided" in _messages(validate_project(good_project), "error")
    (good_project.source / ".batch").write_text("1,1..2\n")
    assert validate_project(good_project) == []


def test_invalid_chapter_range(good_project: Project) -> None:
    good_project.packer.chapter_range = "5..1"
    assert "invalid chapter range" in _messages(validate_project(good_project))


def test_invalid_regex_and_groups(good_project: Project) -> None:
    good_project.packer.chapter_regex = "("
    good_project.packer.extra_regex = r"c(\d+)"
    issues = validate_project(good_project)
    assert "invalid chapter regex" in _messages(issues, "error")
    assert "extra regex has 1 capture group" in _messages(issues, "warning")


def test_unknown_pattern_warning(good_project: Project) -> None:
    good_project.packer.pattern = "nope"
    assert "unknown pattern" in _messages(validate_project(good_project), "warning")


def test_cover_and_kind_warnings(good_project: Project, write_json) -> None:
    write_json(
        good_project.source / "packer.json",
        {"covers": {"1": "covers/v01.webp"}, "kind": "comic"},
    )
    issues = validate_project(good_project)
    assert "cover for volume 1 not found" in _messages(issues, "warning")
    assert "differs from project kind" in _messages(issues, "warning")
    good_project.kind = Kind.COMIC
    assert "differs" not in _messages(validate_project(good_project))


def test_compile_patterns_named_and_custom(good_project: Project) -> None:
    good_project.packer.pattern = "weebcentral"
    chap, extra = compile_patterns(resolve_packer_settings(good_project))
    assert chap is not None and chap.search("# 12")
    good_project.packer.chapter_regex = r"c(\d+)"
    chap, extra = compile_patterns(resolve_packer_settings(good_project))
    assert chap is not None and chap.pattern == r"c(\d+)" and extra is None


def test_convertor_checks(good_project: Project) -> None:
    good_project.convertor = KCCOptions(rotation=7, cropping=9, profile=" ")
    msgs = _messages(validate_project(good_project), "error")
    assert "rotation" in msgs and "cropping" in msgs and "profile is empty" in msgs


def test_convertor_without_packer_needs_dest(good_project: Project, tmp_path) -> None:
    good_project.dest = tmp_path / "out"
    good_project.steps["packer"] = False
    assert "destination folder not found" in _messages(validate_project(good_project))


def test_editor_without_metadata_is_warning(good_project: Project) -> None:
    good_project.editor = EditorOptions()
    issues = validate_project(good_project)
    assert not has_errors(issues)
    assert "will be skipped" in _messages(issues, "warning")


def test_missing_metadata_yaml(good_project: Project, tmp_path: Path) -> None:
    good_project.editor.metadata = tmp_path / "missing.yaml"
    assert "metadata YAML not found" in _messages(validate_project(good_project))


def test_broken_metadata_yaml(good_project: Project, tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("series: [unclosed\n")
    good_project.editor.metadata = bad
    assert "invalid metadata YAML" in _messages(validate_project(good_project))
    bad.write_text("- just\n- a list\n")
    assert "must be a mapping" in _messages(validate_project(good_project))


def test_metadata_locale_warning(good_project: Project) -> None:
    good_project.editor.locale = "french"
    assert "no volume has a `french` block" in _messages(
        validate_project(good_project), "warning"
    )
    good_project.editor.locale = "klingon"
    assert "locale must be one of" in _messages(validate_project(good_project))


def test_chapters_yaml(good_project: Project, tmp_path: Path, write_yaml) -> None:
    good_project.editor.chapters = tmp_path / "missing_chapters.yaml"
    assert "chapters YAML not found" in _messages(validate_project(good_project))
    good_project.editor.chapters = write_yaml(
        tmp_path / "chapters.yaml", {"chapters": [{"number": 1, "title": "A"}]}
    )
    assert validate_project(good_project) == []


def test_chapters_file_key_in_metadata(
    good_project: Project, tmp_path: Path, write_yaml
) -> None:
    write_yaml(
        tmp_path / "meta.yaml",
        {"series": "B", "volumes": [{"english": {}}], "chapters_file": "ch.yaml"},
    )
    assert "chapters YAML not found" in _messages(validate_project(good_project))
    (tmp_path / "ch.yaml").write_text("chapters: 12\n")
    assert "invalid chapters YAML" in _messages(validate_project(good_project))


def test_errors_sorted_first(good_project: Project) -> None:
    good_project.editor = EditorOptions()
    good_project.packer.chapter_regex = "("
    issues = validate_project(good_project)
    assert [i.level for i in issues] == sorted(
        (i.level for i in issues), key=lambda lvl: lvl != "error"
    )
