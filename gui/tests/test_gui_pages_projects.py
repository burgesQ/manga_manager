"""UI tests of the Projects index and the run history page."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from manga_gui.models import Kind, PackerOptions, Project, Settings
from manga_gui.runner import PipelineResult, StepResult
from manga_gui.store import Store
from nicegui.testing import User

pytestmark = pytest.mark.anyio


def _element(user: User, marker: str) -> Any:
    elements = user.find(marker=marker).elements
    assert len(elements) == 1, marker
    return next(iter(elements))


def _set_value(user: User, marker: str, value: Any) -> None:
    element = _element(user, marker)
    with user:
        element.value = value


def _saved(store: Store, tmp_path: Path, name: str = "Saga", **kwargs: Any) -> Project:
    src = kwargs.pop("source", tmp_path / "lib")
    src.mkdir(parents=True, exist_ok=True)
    kwargs.setdefault("packer", PackerOptions(serie="Saga", batch="v01:1..2"))
    project = Project(name=name, source=src, **kwargs)
    store.save_project(project)
    return project


def _result(rc: int = 0, *, dry_run: bool = False) -> PipelineResult:
    return PipelineResult(
        steps=[
            StepResult("packer", ["packer", "--path", "/lib dir"], 0, 1.5),
            StepResult("convertor", ["convertor", "/out"], rc, 2.0),
        ],
        started_at="2026-11-04T10:00:00+01:00",
        duration=3.5,
        dry_run=dry_run,
    )


def _log_lines(user: User) -> list[str]:
    log = _element(user, "history-log")
    return [child.text for child in log.default_slot.children]


# -- projects index ------------------------------------------------------------


async def test_index_shows_last_run_status(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    _saved(gui_store, tmp_path)
    _saved(gui_store, tmp_path, name="Other")
    gui_store.save_run("saga", _result(2, dry_run=True), "log\n")
    await gui_user.open("/")
    await gui_user.should_see(marker="project-card-saga")
    assert _element(gui_user, "last-run-saga").text == (
        "failed · 2026-11-04 10:00:00 (dry-run)"
    )
    assert _element(gui_user, "last-run-other").text == "never run"
    gui_user.find(marker="history-saga").click()
    await gui_user.should_see("Run history — Saga")


async def test_index_duplicate_project(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    _saved(gui_store, tmp_path, kind=Kind.COMIC)
    await gui_user.open("/")
    gui_user.find(marker="duplicate-saga").click()
    assert _element(gui_user, "duplicate-name").value == "Saga (copy)"
    _set_value(gui_user, "duplicate-name", "Saga")  # same slug: refused
    gui_user.find(marker="duplicate-confirm").click()
    await gui_user.should_see("already exists")
    _set_value(gui_user, "duplicate-name", "Saga Deluxe")
    gui_user.find(marker="duplicate-confirm").click()
    await gui_user.should_see(marker="project-link-saga-deluxe")
    copy = gui_store.load_project("saga-deluxe")
    assert copy.kind is Kind.COMIC and copy.packer.batch == "v01:1..2"


@pytest.mark.parametrize("purge", [False, True])
async def test_index_delete_project(
    gui_user: User, gui_store: Store, tmp_path: Path, purge: bool
) -> None:
    _saved(gui_store, tmp_path)
    gui_store.save_run("saga", _result(), "")
    await gui_user.open("/")
    gui_user.find(marker="delete-saga").click()
    if purge:
        gui_user.find(marker="delete-purge").click()
    gui_user.find(marker="delete-confirm").click()
    await gui_user.should_not_see(marker="project-card-saga")
    assert not gui_store.has_project("saga")
    assert (gui_store.list_runs("saga") == []) is purge
    assert (tmp_path / "lib").is_dir()  # the library is never touched


async def test_index_create_from_folder_prefills(
    gui_user: User, gui_store: Store, tmp_path: Path, make_library, write_json
) -> None:
    src = make_library(tmp_path / "lib", ["Chapter 1.cbz"])
    write_json(
        src / "packer.json", {"serie": "Saga", "pattern": "mangafox", "kind": "comic"}
    )
    (src / ".batch").write_text("v01,1\n")
    await gui_user.open("/")
    gui_user.find(marker="new-name").type("Saga")
    gui_user.find(marker="new-source").type(str(src))
    await gui_user.should_see("Batch file: .batch (1 volume(s))")
    await gui_user.should_see("1 .cbz archive(s)")
    assert _element(gui_user, "new-kind").value == "comic"
    gui_user.find(marker="new-create").click()
    await gui_user.should_see(marker="project-name")
    project = gui_store.load_project("saga")
    assert project.kind is Kind.COMIC
    assert project.packer.config == src / "packer.json"
    assert (project.packer.serie, project.packer.pattern) == ("Saga", "mangafox")
    assert project.packer.batch_file is None  # packer finds .batch on its own


# -- history -------------------------------------------------------------------


async def test_history_lists_runs_and_shows_detail(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    _saved(gui_store, tmp_path)
    old = gui_store.save_run("saga", _result(), "old run\n")
    new = gui_store.save_run("saga", _result(2, dry_run=True), "line 1\nline 2\n")
    await gui_user.open("/project/saga")
    gui_user.find(marker="history-link").click()
    await gui_user.should_see("2 run(s)")
    await gui_user.should_see("convertor: 2")
    assert _element(gui_user, "run-status-" + new.run_id).text == "failed"
    assert _element(gui_user, "run-status-" + old.run_id).text == "ok"
    await gui_user.should_see("Select a run to see its commands and log")

    gui_user.find(marker=f"run-open-{new.run_id}").click()
    await gui_user.should_see(marker="history-log")
    assert _log_lines(gui_user) == ["line 1", "line 2"]
    assert _element(gui_user, "run-argv-packer").content == "packer --path '/lib dir'"
    await gui_user.should_see("convertor: exit code 2, 2.0s")

    gui_user.find(marker=f"run-delete-{new.run_id}").click()
    gui_user.find(marker="run-delete-confirm").click()
    await gui_user.should_see("1 run(s)")
    assert [r.run_id for r in gui_store.list_runs("saga")] == [old.run_id]
    await gui_user.should_not_see(marker="history-log")


async def test_history_open_run_from_query_and_orphans(
    gui_user: User, gui_store: Store
) -> None:
    record = gui_store.save_run("gone", _result(), "")
    await gui_user.open(f"/project/gone/history?run={record.run_id}")
    await gui_user.should_see("Project 'gone' not found: showing its remaining runs")
    await gui_user.should_see("(empty log)")
    await gui_user.open("/project/BAD!/history")
    await gui_user.should_see("Invalid project")


# -- library: settings, import, From library ----------------------------------


async def test_library_import_dialog(
    gui_user: User, gui_store: Store, tmp_path: Path, fake_shelf
) -> None:
    gui_store.save_project(Project(name="Berserk", source=tmp_path / "elsewhere"))
    await gui_user.open("/")
    assert _element(gui_user, "library-root").value == ""
    _set_value(gui_user, "library-root", str(fake_shelf.root))
    _set_value(gui_user, "metadata-dir", str(fake_shelf.meta))
    gui_user.find(marker="library-save").click()
    assert gui_store.load_settings().library_root == fake_shelf.root

    gui_user.find(marker="library-import").click()
    await gui_user.should_see(marker="import-select-zetman")
    await gui_user.should_see(
        "key 'boruto_bv' matches the initials of 'BorutoBlueVortex'"
    )
    await gui_user.should_see(marker="import-exists-berserk")
    # preselected: importable and not existing
    assert _element(gui_user, "import-select-zetman").value is True
    assert _element(gui_user, "import-select-berserk").value is False
    orphan = _element(gui_user, "import-select-vinland-saga")
    assert orphan.value is False and not orphan.enabled
    # unselect one
    _set_value(gui_user, "import-select-mashle", False)
    gui_user.find(marker="import-confirm").click()
    await gui_user.should_see("Import: 7 created, 0 overwritten, 0 skipped (exists)")
    await gui_user.should_see(marker="project-card-zetman")
    assert not gui_store.has_project("mashle")
    assert gui_store.load_project("berserk").source == tmp_path / "elsewhere"
    zetman = gui_store.load_project("zetman")
    assert zetman.kind is Kind.COMIC
    assert zetman.editor.metadata == fake_shelf.meta / "zetman.yaml"


async def test_library_import_overwrite(
    gui_user: User, gui_store: Store, tmp_path: Path, fake_shelf
) -> None:
    gui_store.save_project(Project(name="Berserk", source=tmp_path / "elsewhere"))
    await gui_user.open("/")
    _set_value(gui_user, "library-root", str(fake_shelf.root))
    gui_user.find(marker="library-import").click()
    await gui_user.should_see(marker="import-select-berserk")
    _set_value(gui_user, "import-select-berserk", True)
    _set_value(gui_user, "import-overwrite", True)
    gui_user.find(marker="import-confirm").click()
    await gui_user.should_see("1 overwritten")
    assert (
        gui_store.load_project("berserk").source == fake_shelf.root / "EN" / "Berserk"
    )
    assert gui_store.load_settings().library_root is None  # not saved


async def test_library_import_needs_a_folder(gui_user: User) -> None:
    await gui_user.open("/")
    gui_user.find(marker="library-import").click()
    await gui_user.should_see("Set a library root and / or a metadata dir")


async def test_new_project_from_library(
    gui_user: User, gui_store: Store, fake_shelf
) -> None:
    await gui_user.open("/")
    await gui_user.should_not_see(marker="new-library")  # no library root yet
    gui_store.save_settings(
        Settings(library_root=fake_shelf.root, metadata_dir=fake_shelf.meta)
    )
    await gui_user.open("/")
    select = _element(gui_user, "new-library")
    assert select.visible
    src = fake_shelf.root / "EN" / "Zetman"
    assert select.options[str(src)] == "EN/Zetman"
    assert len(select.options) == 9
    _set_value(gui_user, "new-library", str(src))
    assert _element(gui_user, "new-source").value == str(src)
    assert _element(gui_user, "new-name").value == "Zetman"
    assert _element(gui_user, "new-kind").value == "comic"
    await gui_user.should_see("Library: covers of packer_zetman.json are in EN/Zetman")
    await gui_user.should_see("Warning: metadata YAML volumes have no `english` block")
    gui_user.find(marker="new-create").click()
    await gui_user.should_see(marker="project-name")
    project = gui_store.load_project("zetman")
    assert project.source == src and project.kind is Kind.COMIC
    assert project.packer.config == fake_shelf.meta / "packer_zetman.json"
    assert project.editor.metadata == fake_shelf.meta / "zetman.yaml"
    assert project.editor.chapters is None
