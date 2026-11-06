"""UI tests of the pages with NiceGUI's simulated user (see ``gui_user``)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from manga_gui.models import EditorOptions, Kind, PackerOptions, Project
from manga_gui.store import Store
from nicegui import ui
from nicegui.testing import User

pytestmark = pytest.mark.anyio

_PACKER_ONLY = {"packer": True, "convertor": False, "editor": False}


def _element(user: User, marker: str) -> Any:
    elements = user.find(marker=marker).elements
    assert len(elements) == 1, marker
    return next(iter(elements))


def _set_value(user: User, marker: str, value: Any) -> None:
    element = _element(user, marker)
    with user:
        element.value = value


def _saved(store: Store, tmp_path: Path, **kwargs: Any) -> Project:
    src = kwargs.pop("source", tmp_path / "lib")
    src.mkdir(parents=True, exist_ok=True)
    kwargs.setdefault("packer", PackerOptions(serie="Saga", batch="v01:1..2"))
    project = Project(name="Saga", source=src, **kwargs)
    store.save_project(project)
    return project


async def test_index_lists_and_creates_projects(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    _saved(gui_store, tmp_path)
    await gui_user.open("/")
    await gui_user.should_see(marker="project-link-saga")
    gui_user.find(marker="new-name").type("Berserk Deluxe")
    gui_user.find(marker="new-source").type(str(tmp_path / "berserk"))
    gui_user.find(marker="new-create").click()
    await gui_user.should_see(marker="project-name")
    assert gui_store.load_project("berserk-deluxe").source == tmp_path / "berserk"
    # same slug again is refused
    await gui_user.open("/")
    gui_user.find(marker="new-name").type("Saga")
    gui_user.find(marker="new-source").type(str(tmp_path))
    gui_user.find(marker="new-create").click()
    await gui_user.should_see("already exists")


async def test_open_saved_project_page(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    project = _saved(gui_store, tmp_path)
    await gui_user.open(f"/project/{project.slug}")
    await gui_user.should_see(marker="project-name")
    assert _element(gui_user, "source").value == str(project.source)
    assert _element(gui_user, "packer-serie").value == "Saga"
    assert _element(gui_user, "kind-toggle").value == "manga"
    assert _element(gui_user, "volume-mode").value == "spec"
    await gui_user.should_see("Reading direction: Right-to-left (manga)")


async def test_unknown_project(gui_user: User) -> None:
    await gui_user.open("/project/nope")
    await gui_user.should_see("Project not found: nope")


async def test_kind_toggle_sets_comic_preset(
    gui_user: User, gui_store: Store, tmp_path: Path, write_json
) -> None:
    project = _saved(gui_store, tmp_path)
    cfg = write_json(project.source / "packer.json", {"serie": "Saga"})
    await gui_user.open(f"/project/{project.slug}")
    await gui_user.should_see(content="--preset manga")

    _set_value(gui_user, "kind-toggle", "comic")

    await gui_user.should_see(content="--preset comic")
    await gui_user.should_not_see(content="--preset manga")
    await gui_user.should_see("Reading direction: Left-to-right (comic)")
    assert json.loads(cfg.read_text()) == {"serie": "Saga", "kind": "comic"}
    assert '"kind": "comic"' in _element(gui_user, "packer-json-editor").value
    gui_user.find(marker="save-project").click()
    assert gui_store.load_project(project.slug).kind is Kind.COMIC


async def test_kind_toggle_without_packer_json_creates_nothing(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    project = _saved(gui_store, tmp_path)
    await gui_user.open(f"/project/{project.slug}")
    _set_value(gui_user, "kind-toggle", "comic")
    await gui_user.should_see(content="--preset comic")
    assert not (project.source / "packer.json").exists()


async def test_review_shows_generated_commands(
    gui_user: User, gui_store: Store, tmp_path: Path, write_yaml
) -> None:
    meta = write_yaml(tmp_path / "saga.yaml", {"series": "Saga", "volumes": []})
    project = _saved(
        gui_store, tmp_path, dest=tmp_path / "out", editor=EditorOptions(metadata=meta)
    )
    await gui_user.open(f"/project/{project.slug}")
    await gui_user.should_see(marker="command-packer")
    packer_cmd = _element(gui_user, "command-packer").content
    assert packer_cmd.startswith("packer --path ")
    assert "--batch v01:1..2" in packer_cmd
    convertor_cmd = _element(gui_user, "command-convertor").content
    assert convertor_cmd.startswith(f"convertor {tmp_path / 'out'} --preset manga")
    assert _element(gui_user, "command-editor").content.startswith("editor inject")

    gui_user.find(marker="step-editor").click()  # disable the editor step
    await gui_user.should_not_see(marker="command-editor")
    assert gui_store.load_project(project.slug).steps["editor"] is True
    gui_user.find(marker="save-project").click()
    assert gui_store.load_project(project.slug).steps["editor"] is False


async def test_dry_run_packer_saves_run(
    gui_user: User, gui_store: Store, tmp_path: Path, make_library
) -> None:
    src = make_library(tmp_path / "lib", ["Chapter 1.cbz", "Chapter 2.cbz"])
    project = _saved(
        gui_store, tmp_path, source=src, dest=tmp_path / "out", steps=_PACKER_ONLY
    )
    await gui_user.open(f"/project/{project.slug}")
    gui_user.find(marker="dry-run").click()

    for _ in range(300):
        runs = gui_store.list_runs(project.slug)
        if runs:
            break
        await asyncio.sleep(0.05)
    assert runs, "dry-run did not finish"
    result = runs[0].result
    assert result.ok and result.dry_run
    assert [s.step for s in result.steps] == ["packer"]
    log = runs[0].log_path.read_text()
    assert "--dry-run" in log and "[2/2]" in log
    await gui_user.should_see("packer: ok")
    assert _element(gui_user, "run-progress").value == 1
    assert not (tmp_path / "out").exists()


async def test_run_blocked_by_errors(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    project = _saved(gui_store, tmp_path, packer=PackerOptions())  # no serie
    await gui_user.open(f"/project/{project.slug}")
    await gui_user.should_see(content="serie is required")
    assert not _element(gui_user, "run").enabled
    assert _element(gui_user, "dry-run").enabled


async def test_scan_lists_chapters(
    gui_user: User, gui_store: Store, tmp_path: Path, make_library
) -> None:
    src = make_library(tmp_path / "lib", ["Chapter 1.cbz", "Chapter 2.cbz", "x.cbz"])
    project = _saved(gui_store, tmp_path, source=src)
    await gui_user.open(f"/project/{project.slug}")
    gui_user.find(marker="scan").click()
    await gui_user.should_see("2 chapter file(s) detected, 1 unmatched")
    await gui_user.should_see("Unmatched: x.cbz")
    table = _element(gui_user, "scan-table")
    assert [r["number"] for r in table.rows] == [1, 2]


async def test_batch_table_writes_batch_file(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    project = _saved(gui_store, tmp_path, packer=PackerOptions(serie="Saga"))
    await gui_user.open(f"/project/{project.slug}")
    assert _element(gui_user, "volume-mode").value == "file"
    gui_user.find(marker="batch-add").click()
    gui_user.find(marker="batch-chapters-0").type("1..12")
    gui_user.find(marker="batch-save").click()
    assert (project.source / ".batch").read_text() == "v01,1..12\n"
    await gui_user.should_see(marker="cover-1")


async def test_batch_table_updates_spec(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    project = _saved(gui_store, tmp_path)
    await gui_user.open(f"/project/{project.slug}")
    gui_user.find(marker="batch-add").click()
    gui_user.find(marker="batch-chapters-1").type("3..4")
    gui_user.find(marker="batch-save").click()
    assert _element(gui_user, "batch-spec").value == "v01:1..2-v02:3..4"
    gui_user.find(marker="save-project").click()
    assert gui_store.load_project(project.slug).packer.batch == "v01:1..2-v02:3..4"


async def test_volume_mode_switch(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    project = _saved(gui_store, tmp_path)
    await gui_user.open(f"/project/{project.slug}")
    _set_value(gui_user, "volume-mode", "single")
    _set_value(gui_user, "single-volume", 3)
    _set_value(gui_user, "single-range", "1..5")
    gui_user.find(marker="save-project").click()
    opts = gui_store.load_project(project.slug).packer
    assert (opts.batch, opts.volume, opts.chapter_range) == (None, 3, "1..5")
    _set_value(gui_user, "volume-mode", "spec")
    assert _element(gui_user, "batch-spec").value == "v01:1..2"


async def test_packer_json_editor_validates(
    gui_user: User, gui_store: Store, tmp_path: Path, write_json
) -> None:
    project = _saved(gui_store, tmp_path)
    cfg = write_json(project.source / "packer.json", {"serie": "Saga"})
    await gui_user.open(f"/project/{project.slug}")
    _set_value(gui_user, "packer-json-editor", '{"kind": "novel"}')
    gui_user.find(marker="packer-json-save").click()
    await gui_user.should_see("Not saved")
    assert json.loads(cfg.read_text()) == {"serie": "Saga"}
    _set_value(gui_user, "packer-json-editor", '{"serie": "New"}\n')
    gui_user.find(marker="packer-json-save").click()
    assert json.loads(cfg.read_text()) == {"serie": "New"}


async def test_covers_grid_saves_and_shows_thumbnail(
    gui_user: User, gui_store: Store, tmp_path: Path, write_json
) -> None:
    project = _saved(gui_store, tmp_path)
    cfg = write_json(project.source / "packer.json", {"serie": "Saga"})
    (project.source / "c1.webp").write_bytes(b"RIFF0000WEBP")
    await gui_user.open(f"/project/{project.slug}")
    _set_value(gui_user, "cover-1", "c1.webp")
    gui_user.find(marker="covers-save").click()
    assert json.loads(cfg.read_text()) == {
        "serie": "Saga",
        "covers": {"1": "c1.webp"},
    }
    await gui_user.should_see(ui.image)


async def test_metadata_preview_and_save(
    gui_user: User, gui_store: Store, tmp_path: Path, write_yaml
) -> None:
    meta = write_yaml(
        tmp_path / "saga.yaml",
        {
            "series": "Saga",
            "author": "Brian K. Vaughan",
            "chapters": [{"number": 1, "title": "Chapter One"}],
            "volumes": [
                {
                    "number": 1,
                    "title": "Volume One",
                    "english": {"isbn": "978-1", "release_date": "2012-10-10"},
                }
            ],
        },
    )
    project = _saved(gui_store, tmp_path, editor=EditorOptions(metadata=meta))
    await gui_user.open(f"/project/{project.slug}")
    assert _element(gui_user, "meta-series").value == "Saga"
    rows = _element(gui_user, "volumes-table").rows
    assert rows == [
        {
            "number": 1,
            "title": "Volume One",
            "isbn": "978-1",
            "release_date": "2012-10-10",
        }
    ]
    assert _element(gui_user, "chapters-table").rows == [
        {"number": 1, "title": "Chapter One"}
    ]
    await gui_user.should_see("Source: inline chapters")

    _set_value(gui_user, "meta-kind", "comic")
    gui_user.find("Apply to YAML editor").click()
    assert "kind: comic" in _element(gui_user, "metadata-editor").value
    gui_user.find(marker="metadata-save").click()
    assert "kind: comic" in meta.read_text()

    _set_value(gui_user, "metadata-editor", "- not a mapping\n")
    gui_user.find(marker="metadata-save").click()
    await gui_user.should_see("Not saved")
    assert "kind: comic" in meta.read_text()
