"""Tooltips built from the CLIs' argparse parsers (``manga_gui.help_texts``)."""

from __future__ import annotations

import argparse

import pytest
from manga_gui import help_texts
from manga_gui.help_texts import (
    PARSERS,
    all_keys,
    editor_inject_parser,
    field_help,
    find_action,
)


@pytest.mark.parametrize(
    ("tool", "field", "option"),
    [
        (tool, field, option)
        for tool, (_getter, options) in PARSERS.items()
        for field, option in options.items()
    ],
)
def test_every_mapped_option_exists_in_its_parser(
    tool: str, field: str, option: str
) -> None:
    get_parser, _options = PARSERS[tool]
    action = find_action(get_parser(), option)
    assert action.help, f"{tool} {option} has no help text"
    assert field_help(f"{tool}.{field}")


def test_help_comes_from_the_cli_parser() -> None:
    parser_help = find_action(help_texts.packer_parser(), "--serie").help
    assert parser_help is not None
    text = field_help("packer.serie")
    assert text.endswith("[packer --serie]")
    assert parser_help[1:] in text  # same wording as `packer --help`
    assert field_help("convertor.hq").endswith("[convertor --hq]")
    assert field_help("editor.locale").endswith("[editor inject --locale]")
    assert field_help("editor.metadata").endswith("[editor inject <metadata>]")


def test_every_key_has_a_text() -> None:
    keys = all_keys()
    assert "gui.theme" in keys and "packer.pattern" in keys
    assert all(field_help(key).strip() for key in keys)


@pytest.mark.parametrize("key", ["packer.nope", "gui.nope", "nope.serie", "serie"])
def test_unknown_key_raises(key: str) -> None:
    with pytest.raises(KeyError):
        field_help(key)


def test_find_action_unknown_option() -> None:
    with pytest.raises(KeyError, match="--nope"):
        find_action(help_texts.packer_parser(), "--nope")


def test_editor_parser_capture_restores_parse_args() -> None:
    original = argparse.ArgumentParser.parse_args
    editor_inject_parser.cache_clear()
    parser = editor_inject_parser()
    assert argparse.ArgumentParser.parse_args is original
    assert find_action(parser, "--chapters").dest == "chapters"
