"""Effective packer values and wizard navigation helpers of ``manga_gui.forms``."""

from __future__ import annotations

from pathlib import Path

import pytest
from manga_gui.forms import (
    STEP_FIELDS,
    EffectiveField,
    blocking_issues,
    effective_packer_fields,
    field_errors,
    inherited_hint,
    is_forward,
)
from manga_gui.models import PackerOptions, Project
from manga_gui.validation import Issue


def _project(tmp_path: Path, **packer) -> Project:
    src = tmp_path / "lib"
    src.mkdir(exist_ok=True)
    return Project(name="JJK", source=src, packer=PackerOptions(**packer))


# -- effective_packer_fields -------------------------------------------------


def test_effective_without_packer_json(tmp_path: Path) -> None:
    fields = effective_packer_fields(_project(tmp_path))
    assert fields["pattern"] == EffectiveField("default", "default")
    assert fields["serie"] == EffectiveField(None, "default")
    assert fields["nb_worker"] == EffectiveField(1, "default")


def test_effective_inherits_from_packer_json(tmp_path: Path, write_json) -> None:
    project = _project(tmp_path)
    write_json(
        project.source / "packer.json",
        {
            "serie": "Jujutsu Kaisen",
            "pattern": "mangafox",
            "nb_worker": 4,
            "chapter_regex": r"Ch\.(\d+)",
            "batch_file": "vols.csv",
        },
    )
    fields = effective_packer_fields(project)
    assert fields["pattern"] == EffectiveField("mangafox", "packer.json", "mangafox")
    assert fields["serie"].value == "Jujutsu Kaisen"
    assert fields["serie"].source == "packer.json"
    assert fields["nb_worker"] == EffectiveField(4, "packer.json", 4)
    assert fields["chapter_regex"].source == "packer.json"
    assert fields["extra_regex"] == EffectiveField(None, "default")
    # resolved relative to the packer.json folder, like packer does
    assert fields["batch_file"].value == project.source / "vols.csv"
    assert fields["batch_file"].source == "packer.json"


def test_effective_project_value_overrides(tmp_path: Path, write_json) -> None:
    project = _project(tmp_path, pattern="animeSama", serie="JJK", nb_worker=2)
    write_json(
        project.source / "packer.json",
        {"serie": "Jujutsu Kaisen", "pattern": "mangafox"},
    )
    fields = effective_packer_fields(project)
    assert fields["pattern"] == EffectiveField("animeSama", "project", "mangafox")
    assert fields["serie"] == EffectiveField("JJK", "project", "Jujutsu Kaisen")
    assert fields["nb_worker"] == EffectiveField(2, "project", None)


def test_effective_explicit_config_path(tmp_path: Path, write_json) -> None:
    cfg = write_json(tmp_path / "meta" / "packer_jjk.json", {"pattern": "mangafire"})
    project = _project(tmp_path, config=cfg)
    assert effective_packer_fields(project)["pattern"].value == "mangafire"


def test_effective_ignores_invalid_packer_json(tmp_path: Path) -> None:
    project = _project(tmp_path, serie="JJK")
    (project.source / "packer.json").write_text("{not json")
    fields = effective_packer_fields(project)
    assert fields["serie"] == EffectiveField("JJK", "project")
    assert fields["pattern"] == EffectiveField("default", "default")


def test_inherited_hint() -> None:
    assert "from packer.json" in str(
        inherited_hint(EffectiveField("x", "packer.json", "x"))
    )
    assert inherited_hint(EffectiveField("x", "project", "x")) is None
    assert inherited_hint(EffectiveField("x", "project")) is None
    assert (
        inherited_hint(EffectiveField(4, "project", 2)) == "overrides packer.json (2)"
    )


# -- navigation ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("old", "new", "forward"),
    [
        ("library", "packer", True),
        ("packer", "volumes", True),
        ("metadata", "packer", False),
        ("packer", "packer", False),
        (None, "convertor", True),
        ("packer", None, False),
        ("bogus", "packer", False),
    ],
)
def test_is_forward(old: str | None, new: str | None, forward: bool) -> None:
    assert is_forward(old, new) is forward


def test_blocking_issues_maps_wizard_steps() -> None:
    issues = [
        Issue("error", "project", "no name"),
        Issue("error", "packer", "no serie"),
        Issue("warning", "packer", "no cbz"),
        Issue("error", "convertor", "bad rotation"),
        Issue("error", "editor", "bad yaml"),
    ]
    assert [i.message for i in blocking_issues(issues, "library")] == ["no name"]
    assert [i.message for i in blocking_issues(issues, None)] == ["no name"]
    assert [i.message for i in blocking_issues(issues, "packer")] == ["no serie"]
    assert [i.message for i in blocking_issues(issues, "convertor")] == ["bad rotation"]
    assert [i.message for i in blocking_issues(issues, "metadata")] == ["bad yaml"]
    assert blocking_issues(issues, "review") == []
    assert blocking_issues(issues, "volumes") == []


# -- field_errors -------------------------------------------------------------


def test_field_errors_valid_project(tmp_path: Path) -> None:
    project = _project(tmp_path, serie="JJK", batch="v01:1..3")
    assert field_errors(project) == {}


def test_field_errors_serie_from_packer_json_is_enough(
    tmp_path: Path, write_json
) -> None:
    project = _project(tmp_path, batch="v01:1..3")
    assert "packer.json has no serie" in field_errors(project)["serie"]
    write_json(project.source / "packer.json", {"serie": "Jujutsu Kaisen"})
    assert "serie" not in field_errors(project)


def test_field_errors_library(tmp_path: Path) -> None:
    project = Project(name=" ", source=tmp_path / "missing")
    errors = field_errors(project)
    assert errors["name"] == "Required"
    assert errors["source"] == "folder not found"


def test_field_errors_spec_mode(tmp_path: Path) -> None:
    project = _project(tmp_path, serie="JJK")
    assert field_errors(project, "spec") == {"batch": "Required"}
    project.packer.batch = "x1:2"
    assert "invalid batch spec" in field_errors(project)["batch"]


def test_field_errors_single_mode(tmp_path: Path) -> None:
    project = _project(tmp_path, serie="JJK")
    assert field_errors(project, "single") == {
        "volume": "Required",
        "chapter_range": "Required",
    }
    project.packer.volume, project.packer.chapter_range = 1, "a..b"
    assert set(field_errors(project, "single")) == {"chapter_range"}


def test_field_errors_file_mode(tmp_path: Path) -> None:
    project = _project(tmp_path, serie="JJK")
    assert "no batch file" in field_errors(project, "file")["batch_file"]
    project.packer.batch_file = tmp_path / "vols.csv"
    assert "file not found" in field_errors(project, "file")["batch_file"]
    project.packer.batch_file.write_text("v01\n")
    assert "invalid batch file" in field_errors(project, "file")["batch_file"]
    project.packer.batch_file.write_text("v01,1..3\n")
    assert field_errors(project, "file") == {}


def test_field_errors_invalid_regex(tmp_path: Path) -> None:
    project = _project(tmp_path, serie="JJK", batch="v01:1", chapter_regex="(")
    assert "invalid regex" in field_errors(project)["chapter_regex"]


def test_step_fields_cover_every_field_error_key(tmp_path: Path) -> None:
    keys = {k for names in STEP_FIELDS.values() for k in names}
    project = Project(name="", source=tmp_path / "missing")
    project.packer.chapter_regex = project.packer.extra_regex = "("
    for mode in ("spec", "file", "single"):
        assert set(field_errors(project, mode)) <= keys
