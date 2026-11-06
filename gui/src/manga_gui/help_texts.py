"""Hover help (tooltips) of the GUI fields.

The texts of fields that map to a CLI option are **not** duplicated here: they are
read from the CLIs' own argparse parsers (``packer.cli._build_parser()``,
``convertor.cli._build_parser()`` and the ``inject`` subparser of ``editor.cli``),
so a reworded ``--help`` shows up in the GUI as is. Only GUI-only fields (project
name, kind, library root …) have their text in :data:`GUI_HELP`.

Keys are ``<tool>.<field>`` (``packer.serie``, ``convertor.hq``,
``editor.locale``) or ``gui.<field>``; :func:`field_help` returns the text of one
key. ``tests/test_gui_help_texts.py`` checks that every mapped option exists in its
parser, so renaming a CLI option breaks a test rather than the UI.

No NiceGUI import here.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from functools import cache
from typing import Any, NoReturn

PACKER_OPTIONS: dict[str, str] = {
    "source": "--path",
    "dest": "--dest",
    "config": "--config",
    "serie": "--serie",
    "pattern": "--pattern",
    "chapter_regex": "--chapter-regex",
    "extra_regex": "--extra-regex",
    "nb_worker": "--nb-worker",
    "force": "--force",
    "batch": "--batch",
    "batch_file": "--batch-file",
    "volume": "--volume",
    "chapter_range": "--chapter-range",
}
"""GUI field → ``packer`` option."""

CONVERTOR_OPTIONS: dict[str, str] = {
    "preset": "--preset",
    "profile": "--profile",
    "manga_style": "--manga-style",
    "hq": "--hq",
    "forcecolor": "--forcecolor",
    "upscale": "--upscale",
    "blackborders": "--blackborders",
    "rotation": "--rotation",
    "cropping": "--cropping",
    "force_regen": "--force-regen",
}
"""GUI field → ``convertor`` option."""

EDITOR_OPTIONS: dict[str, str] = {
    "metadata": "metadata",
    "chapters": "--chapters",
    "locale": "--locale",
    "force": "--force",
}
"""GUI field → ``editor inject`` option (``metadata`` is the positional argument)."""

GUI_HELP: dict[str, str] = {
    "name": "Name of the project in the GUI; its slug (file name of the profile) "
    "is derived from it when the project is created.",
    "kind": "Manga (right-to-left) or comic (left-to-right): picks the convertor "
    "preset and is written as `kind` into an existing packer.json.",
    "library": "Pick a series folder under the library root: fills the source "
    "folder and, when a metadata group matches, the config files.",
    "library_root": "Folder holding the series folders, usually "
    "<root>/<LANG>/<serie> (saved in the GUI settings).",
    "metadata_dir": "Folder of per-series files: packer_<key>.json, <key>.yaml, "
    "chapters_<key>.yaml, vols_<key>.csv (saved in the GUI settings).",
    "import_overwrite": "Replace the profiles of projects that already exist "
    "(their config files are never touched).",
    "import_select": "Create a project profile for this series.",
    "volume_mode": "How packer gets its volumes: one inline batch spec "
    "(--batch), a batch CSV file (--batch-file) or one volume with a chapter "
    "range (--volume / --chapter-range).",
    "batch_volume": "Volume number (vNN).",
    "batch_chapters": 'Chapters of this volume: a packer range, e.g. "1..12" or '
    '"1,3,5..8" (a batch CSV file only keeps "a..b" ranges).',
    "cover": "Cover image of this volume, saved into packer.json `covers` "
    "(relative paths are resolved from the packer.json folder).",
    "autosave": "Save the metadata YAML automatically (after Apply, when leaving "
    "this step and before a run) instead of clicking Save file.",
    "step": "Run this step in Dry-run / Run.",
    "purge_runs": "Also delete the stored runs (commands and logs) of the project.",
    "theme": "Colour theme of the GUI: Auto follows the browser / system setting.",
    "meta.series": "Series name, written as the Calibre series (`series`).",
    "meta.author": "Author(s), written as dc:creator (comma-separated when the "
    "YAML holds a list).",
    "meta.publisher": "Publisher; a per-locale mapping in the YAML shows the "
    "selected locale.",
    "meta.language": 'BCP 47 language of the EPUBs, e.g. "en-US" (editor default).',
    "meta.kind": "manga or comic: adds a Manga / Comic tag (dc:subject).",
    "meta.genre": "Comma-separated genres, written as dc:subject tags.",
}
"""Texts of the fields that have no CLI option (keys without ``gui.``)."""


class _ParserCaptured(Exception):
    def __init__(self, parser: argparse.ArgumentParser) -> None:
        super().__init__("parser captured")
        self.parser = parser


def _capture_parser(main: Callable[[list[str]], Any]) -> argparse.ArgumentParser:
    """Return the parser ``main`` builds, stopping it at ``parse_args``.

    For CLIs that build their parser inline in ``main()`` (``editor.cli``): the
    class attribute ``parse_args`` is swapped for the duration of the call only.
    """

    def _stop(self: argparse.ArgumentParser, *_args: Any, **_kw: Any) -> NoReturn:
        raise _ParserCaptured(self)

    original = argparse.ArgumentParser.parse_args
    argparse.ArgumentParser.parse_args = _stop  # type: ignore[method-assign]
    try:
        main([])
    except _ParserCaptured as captured:
        return captured.parser
    finally:
        argparse.ArgumentParser.parse_args = original  # type: ignore[method-assign]
    raise RuntimeError("the CLI main() did not parse its arguments")


def _subparser(parser: argparse.ArgumentParser, name: str) -> argparse.ArgumentParser:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            sub = action.choices.get(name)
            if isinstance(sub, argparse.ArgumentParser):
                return sub
    raise KeyError(f"no {name!r} subcommand")


@cache
def packer_parser() -> argparse.ArgumentParser:
    from packer.cli import _build_parser

    return _build_parser()


@cache
def convertor_parser() -> argparse.ArgumentParser:
    from convertor.cli import _build_parser

    return _build_parser()


@cache
def editor_inject_parser() -> argparse.ArgumentParser:
    """The ``editor inject`` subparser (``editor.cli`` has no parser builder)."""
    import editor.cli as editor_cli

    builder = getattr(editor_cli, "_build_parser", None)
    parser = builder() if callable(builder) else _capture_parser(editor_cli.main)
    return _subparser(parser, "inject")


PARSERS: dict[str, tuple[Callable[[], argparse.ArgumentParser], dict[str, str]]] = {
    "packer": (packer_parser, PACKER_OPTIONS),
    "convertor": (convertor_parser, CONVERTOR_OPTIONS),
    "editor": (editor_inject_parser, EDITOR_OPTIONS),
}
"""Tool → (parser getter, GUI field → option)."""

_COMMANDS = {"packer": "packer", "convertor": "convertor", "editor": "editor inject"}


def find_action(parser: argparse.ArgumentParser, option: str) -> argparse.Action:
    """Action of ``option`` (``--flag`` or a positional ``dest``) in ``parser``.

    Raises ``KeyError`` when the parser has no such option.
    """
    for action in parser._actions:
        if option in action.option_strings:
            return action
        if not action.option_strings and action.dest == option:
            return action
    raise KeyError(f"{parser.prog}: no option {option!r}")


def _expand(action: argparse.Action) -> str:
    text = action.help or ""
    if "%" in text:  # argparse placeholders, e.g. %(default)s
        try:
            text = text % {**vars(action), "prog": ""}
        except (KeyError, TypeError, ValueError):
            pass
    return " ".join(text.split())


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:]


@cache
def option_help(tool: str, field: str) -> str:
    """Help of the CLI option behind ``<tool>.<field>``, suffixed by the option.

    >>> option_help("packer", "nb_worker")
    'Number of workers (default 1) [packer --nb-worker]'
    """
    get_parser, options = PARSERS[tool]
    option = options[field]
    action = find_action(get_parser(), option)
    label = option if option.startswith("-") else f"<{option}>"
    return f"{_capitalize(_expand(action))} [{_COMMANDS[tool]} {label}]"


def field_help(key: str) -> str:
    """Tooltip text of ``key`` (``packer.serie``, ``gui.theme`` …).

    Raises ``KeyError`` for an unknown key.

    >>> field_help("gui.theme").startswith("Colour theme")
    True
    """
    tool, _, field = key.partition(".")
    if tool == "gui":
        return GUI_HELP[field]
    if tool not in PARSERS:
        raise KeyError(key)
    return option_help(tool, field)


def all_keys() -> list[str]:
    """Every key :func:`field_help` knows."""
    keys = [f"gui.{k}" for k in GUI_HELP]
    for tool, (_getter, options) in PARSERS.items():
        keys += [f"{tool}.{field}" for field in options]
    return keys
