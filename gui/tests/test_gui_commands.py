from __future__ import annotations

from pathlib import Path

import pytest
from manga_gui.commands import StepCommand, build_command, build_commands
from manga_gui.models import (
    EditorOptions,
    KCCOptions,
    Kind,
    PackerOptions,
    Project,
)

PY = "/usr/bin/python3"
SRC = Path("/lib/Berserk")
DST = Path("/out/Berserk")


def _project(**kwargs) -> Project:
    kwargs.setdefault("editor", EditorOptions(metadata=Path("/meta/berserk.yaml")))
    return Project(name="Berserk", source=SRC, dest=DST, **kwargs)


def _by_step(project: Project, **kwargs) -> dict[str, StepCommand]:
    return {c.step: c for c in build_commands(project, python=PY, **kwargs)}


def test_order_and_cwd() -> None:
    cmds = build_commands(_project(), python=PY)
    assert [c.step for c in cmds] == ["packer", "convertor", "editor"]
    assert all(c.cwd == SRC for c in cmds)
    assert [c.argv[:3] for c in cmds] == [
        [PY, "-m", "packer.main"],
        [PY, "-m", "convertor.main"],
        [PY, "-m", "editor.main"],
    ]


def test_packer_minimal() -> None:
    p = _project(packer=PackerOptions(volume=1, chapter_range="1..12"))
    assert _by_step(p)["packer"].argv[3:] == [
        "--path",
        str(SRC),
        "--dest",
        str(DST),
        "--volume",
        "1",
        "--chapter-range",
        "1..12",
        "--loglevel",
        "INFO",
    ]


def test_packer_dest_defaults_to_source() -> None:
    p = Project(name="x", source=SRC)
    argv = build_commands(p, python=PY)[0].argv
    assert argv[3:7] == ["--path", str(SRC), "--dest", str(SRC)]


def test_packer_all_options_dry_run() -> None:
    p = _project(
        packer=PackerOptions(
            config=Path("/cfg/packer.json"),
            serie="Berserk",
            pattern="mangafox",
            chapter_regex=r"c(\d+)",
            extra_regex=r"c(\d+)\.(\d+)",
            nb_worker=3,
            batch="v01:1..3-v02:4..6",
            force=True,
        )
    )
    assert _by_step(p, dry_run=True)["packer"].argv[3:] == [
        "--path",
        str(SRC),
        "--dest",
        str(DST),
        "--config",
        "/cfg/packer.json",
        "--serie",
        "Berserk",
        "--pattern",
        "mangafox",
        "--chapter-regex",
        r"c(\d+)",
        "--extra-regex",
        r"c(\d+)\.(\d+)",
        "--nb-worker",
        "3",
        "--batch",
        "v01:1..3-v02:4..6",
        "--force",
        "--dry-run",
        "--loglevel",
        "INFO",
    ]


def test_packer_batch_file_wins_over_volume() -> None:
    p = _project(
        packer=PackerOptions(
            batch_file=Path("/cfg/b.batch"), volume=1, chapter_range="1..2"
        )
    )
    argv = _by_step(p)["packer"].argv
    assert "--batch-file" in argv and "/cfg/b.batch" in argv
    assert "--volume" not in argv and "--chapter-range" not in argv


def test_packer_batch_wins_over_batch_file() -> None:
    p = _project(packer=PackerOptions(batch="v01:1", batch_file=Path("/b")))
    argv = _by_step(p)["packer"].argv
    assert "--batch" in argv and "--batch-file" not in argv


@pytest.mark.parametrize("kind", [Kind.MANGA, Kind.COMIC])
def test_convertor_preset_only(kind: Kind) -> None:
    p = _project(kind=kind)
    assert _by_step(p)["convertor"].argv[3:] == [str(DST), "--preset", kind.value]


def test_convertor_overrides_dry_run() -> None:
    p = _project(
        kind=Kind.COMIC,
        convertor=KCCOptions(
            profile="KoF",
            manga_style=True,
            hq=False,
            forcecolor=True,
            upscale=False,
            blackborders=True,
            rotation=0,
            cropping=1,
            force_regen=True,
        ),
    )
    assert _by_step(p, dry_run=True)["convertor"].argv[3:] == [
        str(DST),
        "--preset",
        "comic",
        "--profile",
        "KoF",
        "--manga-style",
        "--no-hq",
        "--forcecolor",
        "--rotation",
        "0",
        "--cropping",
        "1",
        "--no-upscale",
        "--blackborders",
        "--force-regen",
        "--dry-run",
    ]


def test_convertor_false_overrides() -> None:
    p = _project(convertor=KCCOptions(manga_style=False, blackborders=False))
    argv = _by_step(p)["convertor"].argv
    assert argv[-2:] == ["--no-manga-style", "--no-blackborders"]


def test_editor_minimal() -> None:
    assert _by_step(_project())["editor"].argv[3:] == [
        "inject",
        str(DST),
        "/meta/berserk.yaml",
        "--locale",
        "english",
    ]


def test_editor_all_options_dry_run() -> None:
    p = _project(
        editor=EditorOptions(
            metadata=Path("/m.yaml"),
            chapters=Path("/c.yaml"),
            locale="japanese",
            force=True,
        )
    )
    assert _by_step(p, dry_run=True)["editor"].argv[3:] == [
        "inject",
        str(DST),
        "/m.yaml",
        "--locale",
        "japanese",
        "--chapters",
        "/c.yaml",
        "--force",
        "--dry-run",
    ]


def test_editor_skipped_without_metadata() -> None:
    p = _project(editor=EditorOptions())
    assert [c.step for c in build_commands(p, python=PY)] == ["packer", "convertor"]
    assert build_command(p, "editor", python=PY) is None


def test_disabled_steps() -> None:
    p = _project(steps={"packer": False, "convertor": True, "editor": False})
    assert [c.step for c in build_commands(p, python=PY)] == ["convertor"]
    p.steps = {"packer": False, "convertor": False, "editor": False}
    assert build_commands(p, python=PY) == []


def test_build_command_unknown_step() -> None:
    with pytest.raises(ValueError):
        build_command(_project(), "bogus")


def test_shell_uses_console_script_and_quotes() -> None:
    p = Project(
        name="x",
        source=Path("/lib/My Serie"),
        packer=PackerOptions(serie="My Serie", volume=1, chapter_range="1..3"),
    )
    cmd = build_commands(p, python=PY)[0]
    assert cmd.shell() == (
        "packer --path '/lib/My Serie' --dest '/lib/My Serie' --serie 'My Serie' "
        "--volume 1 --chapter-range 1..3 --loglevel INFO"
    )


def test_default_python_is_current_interpreter() -> None:
    import sys

    assert build_commands(_project())[0].argv[0] == sys.executable
