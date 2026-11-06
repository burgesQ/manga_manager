"""UI tests of the volume previews (6th step of the project page)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from manga_gui.models import PackerOptions, Project
from manga_gui.runner import PipelineResult, StepResult
from manga_gui.store import Store
from nicegui import ui
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


async def _open_volumes(user: User, slug: str) -> None:
    await user.open(f"/project/{slug}")
    stepper = next(iter(user.find(ui.stepper).elements))
    with user:
        stepper.value = "volumes"
    for _ in range(200):
        if not _element(user, "previews-summary").text.startswith(("Not", "Scan")):
            return
        await asyncio.sleep(0.02)
    raise AssertionError("previews did not load")


async def test_volume_previews(
    gui_user: User,
    gui_store: Store,
    tmp_path: Path,
    make_volume_dir,
    make_epub,
) -> None:
    dest = tmp_path / "out"
    _saved(
        gui_store,
        tmp_path,
        dest=dest,
        packer=PackerOptions(serie="Saga", batch="v01:1-v02:2"),
    )
    make_volume_dir(dest, "Saga v01", chapters=3)
    make_epub(
        dest / "Saga v01.kepub.epub",
        inject={
            "title": "Saga, Vol. 1",
            "series": "Saga",
            "series_index": 1.0,
            "isbn": "9781607066019",
            "language": "en-US",
            "tags": ["Comic"],
        },
    )
    await _open_volumes(gui_user, "saga")
    assert _element(gui_user, "previews-summary").text.endswith(
        "1 volume folder(s), 1 EPUB(s), 1 with injected metadata, 1 not packed yet"
    )
    assert _element(gui_user, "volume-name-0").text == "Saga v01"
    await gui_user.should_see("3 chapter(s)")
    await gui_user.should_see(ui.image)
    assert _element(gui_user, "volume-epub-0").text == "Saga v01.kepub.epub"
    await gui_user.should_see("Series: Saga")
    await gui_user.should_see("Index: 1")
    await gui_user.should_see("ISBN: 9781607066019")
    await gui_user.should_see("Kind: comic")
    assert _element(gui_user, "volume-name-1").text == "Saga v02"
    await gui_user.should_see("not packed yet")

    make_volume_dir(dest, "Saga v02", chapters=1, cover=False)
    gui_user.find(marker="previews-refresh").click()
    await gui_user.should_see("No .kepub.epub yet")
    await gui_user.should_see("1 chapter(s)")


async def test_volume_previews_empty_and_after_run(
    gui_user: User, gui_store: Store, tmp_path: Path, make_library
) -> None:
    src = make_library(tmp_path / "lib", ["Chapter 1.cbz", "Chapter 2.cbz"])
    _saved(
        gui_store,
        tmp_path,
        source=src,
        dest=tmp_path / "out",
        packer=PackerOptions(serie="Saga", batch="v01:1..2"),
        steps={"packer": True, "convertor": False, "editor": False},
    )
    await _open_volumes(gui_user, "saga")
    await gui_user.should_see("not packed yet")
    _element(gui_user, "previews-summary").text = "stale"
    gui_user.find(marker="dry-run").click()
    for _ in range(300):
        if _element(gui_user, "previews-summary").text != "stale":
            break
        await asyncio.sleep(0.05)
    assert "0 volume folder(s)" in _element(gui_user, "previews-summary").text
    assert gui_store.list_runs("saga")
