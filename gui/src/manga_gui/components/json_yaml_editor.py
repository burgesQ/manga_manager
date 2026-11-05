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
        self._saved_text: str | None = None
        """Text last loaded from / written to disk (``None``: nothing loaded yet)."""
        self._status_text = ""
        with ui.column().classes("w-full gap-1"):
            self.status = ui.label().classes("text-caption text-grey-7")
            self.editor = (
                ui.codemirror(
                    "",
                    language=language,  # type: ignore[arg-type]
                    indent="  ",
                    on_change=lambda _: self._show_status(),
                )
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
        self._show_status()

    @property
    def dirty(self) -> bool:
        """True when the editor holds changes not written to disk yet."""
        return self._saved_text is not None and self.text != self._saved_text

    def _show_status(self, text: str | None = None) -> None:
        if text is not None:
            self._status_text = text
        suffix = " (unsaved changes)" if self.dirty else ""
        self.status.text = self._status_text + suffix

    def load(self) -> None:
        """(Re)load the file; a missing file shows the template."""
        path = self._get_path()
        try:
            content = read_text_or(path, self._template)
        except OSError as e:
            ui.notify(f"Cannot read {path}: {e}", type="negative")
            return
        self._saved_text = content
        self.text = content
        if path is None:
            self._show_status("No file configured")
        elif path.is_file():
            self._show_status(f"Editing {path}")
        else:
            self._show_status(f"{path} does not exist yet: Save file creates it")
        if self._on_loaded is not None:
            self._on_loaded(self.text)

    def save(self, *, quiet: bool = False) -> bool:
        """Validate and write the editor content to the configured path.

        Returns ``True`` on success. Errors are always notified; ``quiet`` only
        drops the success notification (used by auto-save).
        """
        path = self._get_path()
        if path is None:
            ui.notify("Set the file path first", type="warning")
            return False
        text = self.text
        try:
            self._save(path, text)
        except (ValueError, OSError) as e:
            ui.notify(f"Not saved: {e}", type="negative", multi_line=True)
            return False
        logger.info("saved %s", path)
        self._saved_text = text
        self._show_status(f"Editing {path}")
        if not quiet:
            ui.notify(f"Saved {path}", type="positive")
        if self._on_saved is not None:
            self._on_saved(text)
        return True
