"""Shared factory fixtures for manga_gui tests."""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from manga_gui.commands import StepCommand
from manga_gui.models import Project
from manga_gui.pages import register_pages
from manga_gui.store import Store
from nicegui.testing import User, user_simulation

from packer.testing import make_cbz as _packer_make_cbz


@pytest.fixture
def make_project() -> Callable[..., Project]:
    """Build a Project for ``source`` (name defaults to ``Berserk``)."""

    def _make(source: Path, *, name: str = "Berserk", **kwargs: Any) -> Project:
        return Project(name=name, source=source, **kwargs)

    return _make


@pytest.fixture
def make_library() -> Callable[..., Path]:
    """Create ``root`` and one ``.cbz`` (with ComicInfo.xml) per file name."""

    def _make(root: Path, names: list[str], *, include_comicinfo: bool = True) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        for name in names:
            _packer_make_cbz(root, name, include_comicinfo=include_comicinfo)
        return root

    return _make


@pytest.fixture
def write_json() -> Callable[[Path, Any], Path]:
    def _write(path: Path, data: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def write_yaml() -> Callable[[Path, Any], Path]:
    def _write(path: Path, data: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def py_cmd(tmp_path: Path) -> Callable[..., StepCommand]:
    """A StepCommand running ``python -c <code>`` in ``tmp_path``."""

    def _make(code: str, *, step: str = "packer") -> StepCommand:
        return StepCommand(step=step, argv=[sys.executable, "-c", code], cwd=tmp_path)

    return _make


# -- NiceGUI user simulation -------------------------------------------------
#
# The ``nicegui.testing.user_plugin`` fixtures are not registered: a
# ``pytest_plugins`` in a non-root conftest is an error, and the plugin's ``user``
# fixture needs an async test runner plus a ``main_file``. Instead NiceGUI's
# documented ``user_simulation()`` context manager is driven through the anyio
# pytest plugin (already installed): mark UI tests with ``@pytest.mark.anyio``.


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def gui_store(tmp_path: Path) -> Store:
    """Store under ``tmp_path/data`` used by the pages of :func:`gui_user`."""
    return Store(tmp_path / "data")


@pytest.fixture
async def gui_user(gui_store: Store) -> AsyncIterator[User]:
    """Simulated NiceGUI user with the manga-gui pages registered on ``gui_store``.

    NiceGUI's reset drops the page modules from ``sys.modules`` on exit; they are
    put back so later imports keep resolving to the module objects (and classes)
    the tests already hold.
    """
    saved = {
        name: mod
        for name, mod in sys.modules.items()
        if name == "manga_gui" or name.startswith("manga_gui.")
    }
    try:
        async with user_simulation() as user:
            register_pages(gui_store)
            yield user
    finally:
        sys.modules.update(saved)
