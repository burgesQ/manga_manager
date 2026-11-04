"""Volume previews: what packer, convertor and editor produced in the destination.

One card per volume (:func:`~manga_gui.volumes.volume_previews`): cover thumbnail,
chapter count, whether its ``.kepub.epub`` exists and, for an existing EPUB, the
metadata injected by the editor. Volumes the batch plans but packer has not
produced yet are shown greyed out.

Reading EPUBs (ebooklib loads the whole archive) runs in a worker thread
(``run.io_bound``); results are cached until the file changes.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from nicegui import run, ui

from ..volumes import VolumePreview, previews_summary, volume_previews
from .covers_grid import THUMB_CLASSES

logger = logging.getLogger(__name__)


class VolumePreviews:
    """Refreshable grid of volume cards for the destination of a project."""

    def __init__(
        self,
        *,
        get_dest: Callable[[], Path],
        get_expected: Callable[[], list[str]] | None = None,
    ) -> None:
        self._get_dest = get_dest
        self._get_expected = get_expected
        self.loaded = False
        with ui.column().classes("w-full gap-2"):
            with ui.row().classes("w-full items-center gap-2"):
                self.summary = ui.label("Not loaded yet").mark("previews-summary")
                ui.space()
                self.refresh_button = ui.button(
                    "Refresh", icon="refresh", on_click=self.refresh
                ).mark("previews-refresh")
            self.grid = ui.row().classes("w-full gap-3").mark("previews-grid")

    @property
    def alive(self) -> bool:
        return not self.grid.is_deleted

    async def refresh(self) -> None:
        """Rescan the destination and rebuild the cards."""
        dest = self._get_dest()
        expected = self._get_expected() if self._get_expected else []
        self.refresh_button.disable()
        self.summary.text = f"Scanning {dest}…"
        try:
            previews = await run.io_bound(volume_previews, dest, expected=expected)
        except Exception as e:  # pragma: no cover - defensive: filesystem errors
            logger.exception("volume preview failed")
            if self.alive:
                self.summary.text = f"Cannot scan {dest}: {e}"
                self.refresh_button.enable()
            return
        if not self.alive:  # page closed meanwhile
            return
        self.refresh_button.enable()
        self.loaded = True
        self.show(dest, previews)

    def show(self, dest: Path, previews: list[VolumePreview]) -> None:
        self.summary.text = f"{dest}: {previews_summary(previews)}"
        self.grid.clear()
        with self.grid:
            if not previews:
                ui.label("No volume folder or EPUB yet: run packer first").classes(
                    "text-grey-7"
                )
            for index, preview in enumerate(previews):
                self._card(index, preview)

    def _card(self, index: int, preview: VolumePreview) -> None:
        card = ui.card().classes("w-64 p-2 gap-1").mark(f"volume-card-{index}")
        if preview.planned:
            card.classes("opacity-50")
        with card:
            ui.label(preview.name).classes("text-bold").mark(f"volume-name-{index}")
            with ui.column().classes("w-full items-center"):
                if preview.cover is not None:
                    ui.image(preview.cover).classes(THUMB_CLASSES).props("fit=contain")
                else:
                    with ui.column().classes(
                        f"{THUMB_CLASSES} items-center justify-center bg-grey-3"
                    ):
                        ui.icon("image_not_supported", size="lg").classes("text-grey-6")
                        ui.label("no cover").classes("text-caption text-grey-7")
            if preview.planned:
                ui.label("not packed yet").classes("text-caption text-grey-7")
            elif preview.folder is not None:
                ui.label(f"{preview.chapters} chapter(s)").classes("text-caption")
            else:
                ui.label("volume folder missing").classes("text-caption text-grey-7")
            self._epub(index, preview)

    def _epub(self, index: int, preview: VolumePreview) -> None:
        marker = f"volume-epub-{index}"
        if preview.epub is None:
            if not preview.planned:
                ui.label("No .kepub.epub yet").classes(
                    "text-caption text-warning"
                ).mark(marker)
            return
        with ui.row().classes("items-center gap-1"):
            ui.icon("menu_book", size="xs").classes("text-positive")
            ui.label(preview.epub.name).classes("text-caption break-all").mark(marker)
        info = preview.epub_info
        if info is None:  # pragma: no cover - metadata always read here
            return
        meta_marker = f"volume-meta-{index}"
        if info.error:
            ui.label(f"Unreadable EPUB: {info.error}").classes(
                "text-caption text-negative"
            ).mark(meta_marker)
            return
        if not info.injected:
            ui.label("No injected metadata").classes("text-caption text-warning")
        with ui.column().classes("gap-0").mark(meta_marker):
            for label, value in info.fields():
                ui.label(f"{label}: {value}").classes("text-caption")
