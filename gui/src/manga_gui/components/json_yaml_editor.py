"""Raw editor (``ui.codemirror``) bound to a real config file on disk."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from nicegui import ui

from ..forms import read_text_or

logger = logging.getLogger(__name__)

SaveFn = Callable[[Path, str], Any]
"""Validate and write ``text`` to ``path``; raise ``ValueError`` to reject it."""


class FileEditor:
    """Load / edit / save one config file (JSON or YAML) in place.

    ``get_path`` is called on every load and save so the target follows the path
    field of the form. ``save`` validates with the CLI loader before writing; the
    real file is never replaced by invalid content.
    """

    def __init__(
        self,
        *,
        language: str,
        get_path: Callable[[], Path | None],
        save: SaveFn,
        template: str,
        marker: str,
        on_loaded: Callable[[str], None] | None = None,
        on_saved: Callable[[str], None] | None = None,
    ) -> None:
        self._get_path = get_path
        self._save = save
        self._template = template
        self._on_loaded = on_loaded
        self._on_saved = on_saved
        with ui.column().classes("w-full gap-1"):
            self.status = ui.label().classes("text-caption text-grey-7")
            self.editor = (
                ui.codemirror("", language=language, indent="  ")  # type: ignore[arg-type]
                .classes("w-full h-96 border")
                .mark(f"{marker}-editor")
            )
            with ui.row():
                ui.button("Reload from disk", icon="refresh", on_click=self.load).props(
                    "flat"
                ).mark(f"{marker}-reload")
                ui.button("Save file", icon="save", on_click=self.save).mark(
                    f"{marker}-save"
                )

    @property
    def text(self) -> str:
        return str(self.editor.value or "")

    @text.setter
    def text(self, value: str) -> None:
        self.editor.value = value

    def load(self) -> None:
        """(Re)load the file; a missing file shows the template."""
        path = self._get_path()
        try:
            self.text = read_text_or(path, self._template)
        except OSError as e:
            ui.notify(f"Cannot read {path}: {e}", type="negative")
            return
        if path is None:
            self.status.text = "No file configured"
        elif path.is_file():
            self.status.text = f"Editing {path}"
        else:
            self.status.text = f"{path} does not exist yet: Save file creates it"
        if self._on_loaded is not None:
            self._on_loaded(self.text)

    def save(self) -> None:
        """Validate and write the editor content to the configured path."""
        path = self._get_path()
        if path is None:
            ui.notify("Set the file path first", type="warning")
            return
        try:
            self._save(path, self.text)
        except (ValueError, OSError) as e:
            ui.notify(f"Not saved: {e}", type="negative", multi_line=True)
            return
        logger.info("saved %s", path)
        self.status.text = f"Editing {path}"
        ui.notify(f"Saved {path}", type="positive")
        if self._on_saved is not None:
            self._on_saved(self.text)
