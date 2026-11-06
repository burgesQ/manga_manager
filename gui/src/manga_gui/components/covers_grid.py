"""Per-volume cover thumbnails with an editable path (``packer.json`` covers).

Thumbnails of arbitrary local files are served with ``ui.image(Path)``: NiceGUI
registers each file as a media route (``app.add_media_file``) and removes the
route when the element is deleted, so only the configured covers are exposed.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from nicegui import ui

from ..forms import CoverRow, resolve_cover

THUMB_CLASSES = "w-32 h-44 rounded"


class CoversGrid:
    """Grid of cards: volume, thumbnail and cover path input."""

    def __init__(self, *, on_save: Callable[[dict[int, str]], None]) -> None:
        self._values: dict[int, str] = {}
        self._thumbs: dict[int, ui.element] = {}
        self._config_path = Path("packer.json")
        self._on_save = on_save
        with ui.column().classes("w-full gap-2"):
            self._grid = ui.row().classes("w-full gap-3").mark("covers-grid")
            ui.button(
                "Save covers to packer.json",
                icon="save",
                on_click=lambda: self._on_save(dict(self._values)),
            ).mark("covers-save")

    def set_rows(self, config_path: Path, rows: list[CoverRow]) -> None:
        """Show ``rows``; relative paths resolve against ``config_path``'s folder."""
        self._config_path = config_path
        self._values = {r.volume: r.raw for r in rows}
        self._thumbs.clear()
        self._grid.clear()
        with self._grid:
            if not rows:
                ui.label("No volume: fill the batch table first").classes("text-grey-7")
            for row in rows:
                with ui.card().classes("items-center p-2 gap-1"):
                    ui.label(f"Volume {row.volume}").classes("text-bold")
                    self._thumbs[row.volume] = ui.column().classes("items-center")
                    self._render_thumb(row.volume)
                    ui.input(
                        "Cover path",
                        value=row.raw,
                        on_change=lambda e, v=row.volume: self._set(v, e.value),
                    ).classes("w-48").mark(f"cover-{row.volume}").on(
                        "blur", lambda v=row.volume: self._render_thumb(v)
                    )

    def _set(self, volume: int, value: str | None) -> None:
        self._values[volume] = value or ""

    def _render_thumb(self, volume: int) -> None:
        box = self._thumbs.get(volume)
        if box is None:
            return
        box.clear()
        path = resolve_cover(self._values.get(volume, ""), self._config_path)
        with box:
            if path is not None and path.is_file():
                ui.image(path).classes(THUMB_CLASSES).props("fit=contain")
            else:
                with ui.column().classes(
                    f"{THUMB_CLASSES} items-center justify-center bg-grey-3"
                ):
                    ui.icon("image_not_supported", size="lg").classes("text-grey-6")
                    ui.label("missing" if path is not None else "no cover").classes(
                        "text-caption text-grey-7"
                    )
