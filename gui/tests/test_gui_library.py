"""Unit tests of ``manga_gui.library`` (projects and runs helpers)."""

from __future__ import annotations

import doctest
from pathlib import Path

import pytest
from manga_gui import library
from manga_gui.forms import StepStatus
from manga_gui.library import (
    create_project,
    describe_detection,
    detect_folder,
    duplicate_project,
    last_run_summary,
    new_project,
    run_status,
    run_summaries,
)
from manga_gui.models import Kind, PackerOptions, Project
from manga_gui.runner import PipelineResult, StepResult
from manga_gui.store import Store


def _result(
    rc: int = 0, *, cancelled: bool = False, dry_run: bool = False
) -> PipelineResult:
    return PipelineResult(
        steps=[
            StepResult("packer", ["packer", "--path", "/lib"], 0, 1.5),
            StepResult("convertor", ["convertor", "/out"], rc, 2.0, cancelled),
        ],
        started_at="2026-11-04T10:00:00+01:00",
        duration=3.5,
        cancelled=cancelled,
        dry_run=dry_run,
    )


def test_doctests() -> None:
    assert doctest.testmod(library).failed == 0


# -- folder detection / create -----------------------------------------------


def test_detect_missing_folder(tmp_path: Path) -> None:
    det = detect_folder(tmp_path / "nope")
    assert not det.exists and det.config_path is None
    assert describe_detection(det)[0].startswith("Folder not found")


def test_detect_packer_json_and_batch(tmp_path: Path, make_library, write_json) -> None:
    src = make_library(tmp_path / "lib", ["Chapter 1.cbz", "Chapter 2.cbz"])
    write_json(
        src / "packer.json",
        {"serie": "Saga", "pattern": "mangafire", "kind": "comic"},
    )
    (src / ".batch").write_text("v01,1..2\nv02,3..4\n")
    det = detect_folder(src)
    assert det.config_path == src / "packer.json"
    assert (det.serie, det.pattern, det.kind) == ("Saga", "mangafire", Kind.COMIC)
    assert det.batch_file == src / ".batch" and det.batch_volumes == 2
    assert det.cbz_count == 2 and det.errors == []
    lines = describe_detection(det)
    assert lines[0] == "2 .cbz archive(s)"
    assert "serie=Saga" in lines[1] and "kind=comic" in lines[1]
    assert lines[2] == "Batch file: .batch (2 volume(s))"


def test_detect_batch_file_from_packer_json(tmp_path: Path, write_json) -> None:
    src = tmp_path / "lib"
    write_json(src / "packer.json", {"batch_file": "vols.csv", "pattern": "nope"})
    (src / "vols.csv").write_text("v01,1\n")
    (src / ".batch").write_text("v01,1\nv02,2\n")
    det = detect_folder(src)
    assert det.batch_file == src / "vols.csv" and det.batch_volumes == 1
    assert det.pattern is None and det.serie is None and det.kind is None


def test_detect_invalid_files(tmp_path: Path) -> None:
    src = tmp_path / "lib"
    src.mkdir()
    (src / "packer.json").write_text("[1]")
    (src / ".batch").write_text("garbage\n")
    det = detect_folder(src)
    assert det.config == {} and det.config_path == src / "packer.json"
    assert len(det.errors) == 2
    assert describe_detection(det)[-1].startswith("Error: invalid batch file")
    # nothing prefilled from an invalid packer.json, but packer.config still set
    project = new_project("X", src, detection=det)
    assert project.packer.serie is None and project.kind is Kind.MANGA


def test_new_project_prefill_and_kind_override(tmp_path: Path, write_json) -> None:
    src = tmp_path / "lib"
    write_json(src / "packer.json", {"serie": "Saga", "kind": "comic"})
    det = detect_folder(src)
    project = new_project("Saga", src, detection=det)
    assert project.packer.config == src / "packer.json"
    assert (project.packer.serie, project.packer.pattern) == ("Saga", "default")
    assert project.kind is Kind.COMIC
    assert new_project("Saga", src, kind=Kind.MANGA, detection=det).kind is Kind.MANGA
    bare = new_project("Saga", src)
    assert bare.packer == PackerOptions()


def test_create_project(tmp_path: Path, write_json) -> None:
    store = Store(tmp_path / "data")
    src = tmp_path / "lib"
    write_json(src / "packer.json", {"serie": "Saga"})
    project = create_project(store, "  Saga  ", str(src), kind=Kind.COMIC)
    loaded = store.load_project("saga")
    assert loaded.name == "Saga" and loaded.kind is Kind.COMIC
    assert loaded.packer.serie == "Saga" == project.packer.serie
    with pytest.raises(ValueError, match="already exists"):
        create_project(store, "saga", str(src))
    with pytest.raises(ValueError, match="name is required"):
        create_project(store, " ", str(src))
    with pytest.raises(ValueError, match="source folder is required"):
        create_project(store, "Other", "  ")
    plain = create_project(store, "Plain", str(src), from_folder=False)
    assert plain.packer.serie is None


def test_duplicate_project(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    src = Project(
        name="Saga",
        source=tmp_path,
        kind=Kind.COMIC,
        packer=PackerOptions(serie="Saga", batch="v01:1"),
    )
    store.save_project(src)
    store.save_run("saga", _result(), "log\n")
    dup = duplicate_project(store, "saga", "Saga Deluxe")
    loaded = store.load_project("saga-deluxe")
    assert loaded == dup
    assert (loaded.name, loaded.kind, loaded.packer) == (
        "Saga Deluxe",
        Kind.COMIC,
        src.packer,
    )
    assert store.list_runs("saga-deluxe") == []
    with pytest.raises(ValueError, match="already exists"):
        duplicate_project(store, "saga", "saga deluxe")
    with pytest.raises(ValueError, match="required"):
        duplicate_project(store, "saga", "")
    with pytest.raises(FileNotFoundError):
        duplicate_project(store, "nope", "New")


# -- runs ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("result", "status"),
    [
        (_result(), StepStatus.OK),
        (_result(2), StepStatus.FAILED),
        (_result(-15, cancelled=True), StepStatus.CANCELLED),
    ],
)
def test_run_status(result: PipelineResult, status: StepStatus) -> None:
    assert run_status(result) is status


def test_run_summaries(tmp_path: Path) -> None:
    store = Store(tmp_path)
    assert last_run_summary(store, "saga") is None
    store.save_run("saga", _result(), "")
    store.save_run("saga", _result(2, dry_run=True), "")
    summaries = run_summaries(store, "saga")
    assert [s.status for s in summaries] == [StepStatus.FAILED, StepStatus.OK]
    last = last_run_summary(store, "saga")
    assert last == summaries[0]
    assert last.dry_run and last.exit_code == 2
    assert [(s.step, s.exit_code, s.status) for s in last.steps] == [
        ("packer", 0, StepStatus.OK),
        ("convertor", 2, StepStatus.FAILED),
    ]
    assert last.label == "failed · 2026-11-04 10:00:00 (dry-run)"
    cancelled = library.summarize_run(
        store.save_run("saga", _result(-15, cancelled=True), "")
    )
    assert cancelled.steps[1].status is StepStatus.CANCELLED
