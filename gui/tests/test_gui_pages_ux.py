"""UI tests: packer.json inherited values, blocked forward navigation, tooltips
and the theme switch (simulated user, see ``gui_user``)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from manga_gui.models import PackerOptions, Project, Settings
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


def _saved(store: Store, tmp_path: Path, **kwargs: Any) -> Project:
    src = kwargs.pop("source", tmp_path / "lib")
    src.mkdir(parents=True, exist_ok=True)
    kwargs.setdefault("packer", PackerOptions(serie="Saga", batch="v01:1..2"))
    project = Project(name="Saga", source=src, **kwargs)
    store.save_project(project)
    return project


def _stepper(user: User) -> Any:
    return next(iter(user.find(ui.stepper).elements))


async def _go_to_step(user: User, name: str) -> None:
    with user:
        _stepper(user).value = name
    await asyncio.sleep(0.05)  # let the async on_value_change handler run


async def _click(user: User, marker: str) -> None:
    user.find(marker=marker).click()
    await asyncio.sleep(0.05)


def _tooltip(user: User, marker: str) -> str:
    """Text of the tooltip attached to the element marked ``marker``."""
    html_id = _element(user, marker).html_id
    targets = {f"#{html_id}", f'[for="{html_id}"]'}  # ui.select anchors on its field
    texts = [
        t.text for t in user.find(ui.tooltip).elements if t.props["target"] in targets
    ]
    assert len(texts) == 1, f"{marker}: {len(texts)} tooltip(s)"
    return texts[0]


# -- packer step: values inherited from packer.json ---------------------------


async def test_packer_step_shows_packer_json_values(
    gui_user: User, gui_store: Store, tmp_path: Path, write_json
) -> None:
    project = _saved(gui_store, tmp_path, packer=PackerOptions(batch="v01:1..2"))
    write_json(
        project.source / "packer.json",
        {"serie": "Jujutsu Kaisen", "pattern": "mangafox", "nb_worker": 4},
    )
    await gui_user.open(f"/project/{project.slug}")
    pattern = _element(gui_user, "packer-pattern")
    assert pattern.value == "mangafox"
    assert "from packer.json" in pattern.props["hint"]
    assert pattern.options["default"] == "default (use packer.json: mangafox)"
    serie = _element(gui_user, "packer-serie")
    assert serie.value == ""
    assert serie.props["placeholder"] == "Jujutsu Kaisen"
    assert "from packer.json" in serie.props["hint"]
    assert _element(gui_user, "packer-workers").value == 4

    # displaying the inherited values does not copy them into the project
    gui_user.find(marker="save-project").click()
    saved = gui_store.load_project(project.slug).packer
    assert (saved.pattern, saved.serie, saved.nb_worker) == ("default", None, 1)

    # changing the pattern overrides packer.json for this project only
    _set_value(gui_user, "packer-pattern", "animeSama")
    assert pattern.props["hint"] == "overrides packer.json (mangafox)"
    gui_user.find(marker="save-project").click()
    assert gui_store.load_project(project.slug).packer.pattern == "animeSama"
    assert json.loads((project.source / "packer.json").read_text())["pattern"] == (
        "mangafox"
    )
    # back to "default": packer.json applies again
    _set_value(gui_user, "packer-pattern", "default")
    assert pattern.value == "mangafox"
    gui_user.find(marker="save-project").click()
    assert gui_store.load_project(project.slug).packer.pattern == "default"


async def test_packer_step_refreshes_after_packer_json_save(
    gui_user: User, gui_store: Store, tmp_path: Path, write_json
) -> None:
    project = _saved(gui_store, tmp_path, packer=PackerOptions(batch="v01:1..2"))
    write_json(project.source / "packer.json", {"serie": "Saga"})
    other = write_json(tmp_path / "meta" / "packer_saga.json", {"serie": "Other"})
    await gui_user.open(f"/project/{project.slug}")
    pattern = _element(gui_user, "packer-pattern")
    assert pattern.value == "default"
    assert "hint" not in pattern.props

    _set_value(
        gui_user, "packer-json-editor", '{"serie": "Saga", "pattern": "mangafire"}'
    )
    gui_user.find(marker="packer-json-save").click()
    assert pattern.value == "mangafire"
    assert "from packer.json" in pattern.props["hint"]

    _set_value(gui_user, "packer-config", str(other))
    assert _element(gui_user, "packer-serie").props["placeholder"] == "Other"
    assert pattern.value == "default"


# -- forward navigation is blocked by errors ------------------------------------


async def test_next_from_packer_blocked_without_serie(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    project = _saved(gui_store, tmp_path, packer=PackerOptions(batch="v01:1..2"))
    await gui_user.open(f"/project/{project.slug}")
    await _click(gui_user, "next-library")
    assert _stepper(gui_user).value == "packer"

    await _click(gui_user, "next-packer")
    assert _stepper(gui_user).value == "packer"
    await gui_user.should_see("Fix Packer before moving on")
    await gui_user.should_see("serie is required")
    assert "packer.json has no serie" in _element(gui_user, "packer-serie").error

    # a later step header is refused too
    await _go_to_step(gui_user, "review")
    assert _stepper(gui_user).value == "packer"

    # backward is always allowed
    await _click(gui_user, "back-packer")
    assert _stepper(gui_user).value == "library"

    # fixed: moving forward works and the highlight is cleared
    await _go_to_step(gui_user, "packer")
    _set_value(gui_user, "packer-serie", "Saga")
    assert _element(gui_user, "packer-serie").error is None
    await _click(gui_user, "next-packer")
    assert _stepper(gui_user).value == "convertor"


async def test_next_from_packer_blocked_by_invalid_batch(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    project = _saved(
        gui_store, tmp_path, packer=PackerOptions(serie="Saga", batch="vx:1")
    )
    await gui_user.open(f"/project/{project.slug}")
    await _go_to_step(gui_user, "packer")
    await _go_to_step(gui_user, "convertor")
    assert _stepper(gui_user).value == "packer"
    await gui_user.should_see("invalid batch")
    assert "invalid batch spec" in _element(gui_user, "batch-spec").error


async def test_warnings_do_not_block(
    gui_user: User, gui_store: Store, tmp_path: Path, write_json
) -> None:
    project = _saved(gui_store, tmp_path)
    # kind mismatch + no .cbz in the source: two packer warnings
    write_json(project.source / "packer.json", {"serie": "Saga", "kind": "comic"})
    await gui_user.open(f"/project/{project.slug}")
    await _go_to_step(gui_user, "packer")
    await _click(gui_user, "next-packer")
    assert _stepper(gui_user).value == "convertor"


async def test_disabled_step_does_not_block(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    project = _saved(
        gui_store,
        tmp_path,
        packer=PackerOptions(),
        steps={"packer": False, "convertor": True, "editor": False},
    )
    (tmp_path / "lib" / "Saga v01").mkdir()
    await gui_user.open(f"/project/{project.slug}")
    await _go_to_step(gui_user, "packer")
    await _click(gui_user, "next-packer")
    assert _stepper(gui_user).value == "convertor"


async def test_library_requires_a_name(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    project = _saved(gui_store, tmp_path)
    await gui_user.open(f"/project/{project.slug}")
    _set_value(gui_user, "project-name", "")
    await _click(gui_user, "next-library")
    assert _stepper(gui_user).value == "library"
    await gui_user.should_see("project name is required")
    assert _element(gui_user, "project-name").error == "Required"


async def test_library_blocked_by_missing_source(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    project = _saved(gui_store, tmp_path)
    await gui_user.open(f"/project/{project.slug}")
    _set_value(gui_user, "source", str(tmp_path / "missing"))
    await _go_to_step(gui_user, "packer")
    assert _stepper(gui_user).value == "library"
    await gui_user.should_see("source folder not found")
    assert _element(gui_user, "source").error == "folder not found"


# -- tooltips -------------------------------------------------------------------


async def test_wizard_tooltips(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    project = _saved(gui_store, tmp_path)
    await gui_user.open(f"/project/{project.slug}")
    assert _tooltip(gui_user, "packer-serie").endswith("[packer --serie]")
    assert "mangafox" in _tooltip(gui_user, "packer-pattern")
    assert _tooltip(gui_user, "kcc-hq").endswith("[convertor --hq]")
    assert _tooltip(gui_user, "kcc-rotation").endswith("[convertor --rotation]")
    assert _tooltip(gui_user, "metadata-locale").endswith("[editor inject --locale]")
    assert _tooltip(gui_user, "source").endswith("[packer --path]")
    assert "slug" in _tooltip(gui_user, "project-name")
    assert "Dry-run" in _tooltip(gui_user, "step-packer")
    assert "batch spec" in _tooltip(gui_user, "volume-mode")


async def test_projects_page_tooltips(gui_user: User) -> None:
    await gui_user.open("/")
    assert _tooltip(gui_user, "new-source").endswith("[packer --path]")
    assert "series folders" in _tooltip(gui_user, "library-root")
    assert "packer_<key>.json" in _tooltip(gui_user, "metadata-dir")
    assert "Manga" in _tooltip(gui_user, "new-kind")
    assert "profiles" in _tooltip(gui_user, "import-overwrite")
    assert "Auto" in _tooltip(gui_user, "theme-switch")


# -- theme ----------------------------------------------------------------------


def _dark_mode(user: User) -> Any:
    elements = user.find(ui.dark_mode).elements
    assert len(elements) == 1
    return next(iter(elements))


async def test_theme_switch_persists_and_applies_on_reload(
    gui_user: User, gui_store: Store, tmp_path: Path
) -> None:
    gui_store.save_settings(Settings(library_root=tmp_path))
    project = _saved(gui_store, tmp_path)
    await gui_user.open("/")
    assert _element(gui_user, "theme-switch").value == "auto"
    assert _dark_mode(gui_user).value is None

    _set_value(gui_user, "theme-switch", "dark")
    assert _dark_mode(gui_user).value is True
    assert gui_store.load_settings() == Settings(library_root=tmp_path, theme="dark")

    # saving the library settings keeps the theme
    gui_user.find(marker="library-save").click()
    assert gui_store.load_settings().theme == "dark"

    for url in (f"/project/{project.slug}", f"/project/{project.slug}/history"):
        await gui_user.open(url)
        assert _element(gui_user, "theme-switch").value == "dark"
        assert _dark_mode(gui_user).value is True

    _set_value(gui_user, "theme-switch", "light")
    await gui_user.open("/")
    assert _dark_mode(gui_user).value is False
    assert gui_store.load_settings().theme == "light"
