from __future__ import annotations

import doctest
import json
from pathlib import Path

import pytest
from manga_gui import models
from manga_gui.models import (
    EditorOptions,
    KCCOptions,
    Kind,
    PackerOptions,
    Project,
    slugify,
)


def test_doctests() -> None:
    assert doctest.testmod(models).failed == 0


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Berserk", "berserk"),
        ("  Jujutsu Kaisen: Modulo  ", "jujutsu-kaisen-modulo"),
        ("Pokémon Adventures", "pokemon-adventures"),
        ("Saga 2012", "saga-2012"),
        ("***", "project"),
    ],
)
def test_slugify(name: str, expected: str) -> None:
    assert slugify(name) == expected


def test_project_defaults(tmp_path: Path) -> None:
    p = Project(name="Mashle Vol", source=tmp_path)
    assert p.slug == "mashle-vol"
    assert p.kind is Kind.MANGA
    assert p.effective_dest == tmp_path
    assert p.steps == {"packer": True, "convertor": True, "editor": True}
    assert p.packer == PackerOptions()
    assert p.convertor.manga_style is None


def test_effective_dest_uses_dest(tmp_path: Path) -> None:
    p = Project(name="x", source=tmp_path, dest=tmp_path / "out")
    assert p.effective_dest == tmp_path / "out"


def test_partial_steps_are_completed(tmp_path: Path) -> None:
    p = Project(name="x", source=tmp_path, steps={"editor": False})
    assert p.steps == {"packer": True, "convertor": True, "editor": False}
    assert not p.step_enabled("editor")
    assert not p.step_enabled("unknown")


def test_round_trip_full(tmp_path: Path) -> None:
    p = Project(
        name="Saga",
        slug="saga-custom",
        kind=Kind.COMIC,
        source=tmp_path / "src",
        dest=tmp_path / "dst",
        packer=PackerOptions(
            config=tmp_path / "packer.json",
            serie="Saga",
            pattern="mangafox",
            chapter_regex=r"#(\d+)",
            extra_regex=r"#(\d+)\.(\d+)",
            nb_worker=4,
            batch_file=tmp_path / "saga.batch",
            force=True,
        ),
        convertor=KCCOptions(
            profile="KoF", manga_style=False, rotation=0, cropping=1, force_regen=True
        ),
        editor=EditorOptions(
            metadata=tmp_path / "saga.yaml",
            chapters=tmp_path / "chapters.yaml",
            locale="french",
            force=True,
        ),
        steps={"packer": True, "convertor": False, "editor": True},
    )
    data = p.to_dict()
    # Must be JSON-serialisable with paths as plain strings.
    text = json.dumps(data)
    assert data["source"] == str(tmp_path / "src")
    assert data["packer"]["batch_file"] == str(tmp_path / "saga.batch")
    assert data["kind"] == "comic"
    assert Project.from_dict(json.loads(text)) == p


def test_round_trip_minimal(tmp_path: Path) -> None:
    p = Project(name="x", source=tmp_path)
    data = p.to_dict()
    assert data["dest"] is None
    assert data["editor"]["metadata"] is None
    assert Project.from_dict(data) == p


def test_from_dict_ignores_unknown_keys_and_empty_paths(tmp_path: Path) -> None:
    data = {
        "name": "x",
        "source": str(tmp_path),
        "future_key": 1,
        "packer": {"serie": "X", "unknown": True, "config": ""},
        "editor": {"metadata": str(tmp_path / "m.yaml")},
    }
    p = Project.from_dict(data)
    assert p.slug == "x"
    assert p.packer.serie == "X"
    assert p.packer.config is None
    assert p.editor.metadata == tmp_path / "m.yaml"
    assert p.kind is Kind.MANGA


def test_kind_is_str_enum() -> None:
    assert Kind("comic") is Kind.COMIC
    assert str(Kind.MANGA) == "manga"
