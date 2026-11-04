"""commands + runner against the real packer CLI (fast: no KCC involved)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from manga_gui.commands import build_commands
from manga_gui.models import PackerOptions, Project
from manga_gui.runner import PipelineRunner, parse_progress

_PACKER_ONLY = {"packer": True, "convertor": False, "editor": False}


def _run(project: Project, *, dry_run: bool) -> tuple[int, list[str]]:
    lines: list[str] = []
    cmds = build_commands(project, dry_run=dry_run)
    result = asyncio.run(PipelineRunner().run(cmds, lines.append, dry_run=dry_run))
    return result.exit_code, lines


def test_packer_dry_run_progress(tmp_path: Path, make_library) -> None:
    src = make_library(tmp_path / "lib", ["Chapter 1.cbz", "Chapter 2.cbz"])
    project = Project(
        name="Berserk",
        source=src,
        dest=tmp_path / "out",
        packer=PackerOptions(serie="Berserk", batch="v01:1..2"),
        steps=_PACKER_ONLY,
    )
    rc, lines = _run(project, dry_run=True)
    assert rc == 0, "\n".join(lines)
    progress = [p for p in map(parse_progress, lines) if p is not None]
    assert progress == [(1, 2), (2, 2)]
    # Plain logs: no ANSI colour codes when not attached to a tty.
    assert not any("\x1b[" in line for line in lines)
    assert not (tmp_path / "out").exists()


def test_packer_real_run(tmp_path: Path, make_library) -> None:
    src = make_library(tmp_path / "lib", ["Chapter 1.cbz", "Chapter 2.cbz"])
    project = Project(
        name="Berserk",
        source=src,
        dest=tmp_path / "out",
        packer=PackerOptions(serie="Berserk", volume=1, chapter_range="1..2"),
        steps=_PACKER_ONLY,
    )
    rc, lines = _run(project, dry_run=False)
    assert rc == 0, "\n".join(lines)
    vol = tmp_path / "out" / "Berserk v01"
    assert (vol / "Chapter 001").is_dir() and (vol / "Chapter 002").is_dir()


def test_packer_cli_error_exit_code(tmp_path: Path, make_library) -> None:
    src = make_library(tmp_path / "lib", ["Chapter 1.cbz"])
    project = Project(
        name="x",
        source=src,
        packer=PackerOptions(volume=1, chapter_range="1"),
        steps=_PACKER_ONLY,
    )
    rc, lines = _run(project, dry_run=True)
    assert rc == 2
    assert any("serie" in line for line in lines)
