"""Editable volume → chapter-range table (the batch CSV / batch spec)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import ui

from ..forms import BatchRow, validate_batch_rows
from ..help_texts import field_help


class BatchTable:
    """Rows of ``(volume, range)`` inputs with add / delete buttons.

    The table only edits rows in memory; the page decides where they are loaded
    from and saved to (batch spec or batch CSV file).
    """

    def __init__(self, *, on_change: Callable[[], None] | None = None) -> None:
        self._rows: list[dict[str, Any]] = []
        self._on_change = on_change
        with ui.column().classes("w-full gap-1"):
            self._body = ui.column().classes("w-full gap-1").mark("batch-rows")
            ui.button("Add volume", icon="add", on_click=self.add_row).props(
                "flat dense"
            ).mark("batch-add")

    def set_rows(self, rows: list[BatchRow]) -> None:
        self._rows = [{"volume": r.volume, "chapters": r.chapters} for r in rows]
        self._render()

    def rows(self) -> list[BatchRow]:
        """Current rows; raises ``ValueError`` when one is incomplete / invalid."""
        out: list[BatchRow] = []
        for i, row in enumerate(self._rows, start=1):
            if row["volume"] is None or not str(row["chapters"]).strip():
                raise ValueError(f"row {i}: volume and chapters are required")
            out.append(BatchRow(int(row["volume"]), str(row["chapters"]).strip()))
        problems = validate_batch_rows(out)
        if problems:
            raise ValueError("; ".join(problems))
        return out

    def volumes(self) -> list[int]:
        """Volume numbers currently typed (incomplete rows skipped)."""
        return [int(r["volume"]) for r in self._rows if r["volume"] is not None]

    def add_row(self) -> None:
        last = self.volumes()
        self._rows.append({"volume": (max(last) + 1) if last else 1, "chapters": ""})
        self._render()
        self._changed()

    def _remove(self, index: int) -> None:
        del self._rows[index]
        self._render()
        self._changed()

    def _changed(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def _set(self, index: int, key: str, value: Any) -> None:
        if key == "volume":
            value = None if value is None else int(value)
        self._rows[index][key] = value

    def _render(self) -> None:
        self._body.clear()
        with self._body:
            if not self._rows:
                ui.label("No volume yet").classes("text-grey-7")
            for i, row in enumerate(self._rows):
                with ui.row().classes("items-center gap-2"):
                    ui.number(
                        "Volume",
                        value=row["volume"],
                        min=0,
                        precision=0,
                        on_change=lambda e, i=i: self._set(i, "volume", e.value),
                    ).classes("w-24").mark(f"batch-volume-{i}").tooltip(
                        field_help("gui.batch_volume")
                    )
                    ui.input(
                        "Chapters (e.g. 1..12)",
                        value=row["chapters"],
                        on_change=lambda e, i=i: self._set(i, "chapters", e.value),
                    ).classes("w-64").mark(f"batch-chapters-{i}").tooltip(
                        field_help("gui.batch_chapters")
                    )
                    ui.button(
                        icon="delete", on_click=lambda i=i: self._remove(i)
                    ).props("flat dense round").tooltip("Remove this volume")
