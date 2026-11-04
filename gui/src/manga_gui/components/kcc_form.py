"""KCC overrides form: each field shows the preset value and an override."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import ui

from ..forms import (
    KCC_BOOL_FIELDS,
    TRI_STATES,
    effective_kcc,
    format_kcc_value,
    from_tri_state,
    kcc_preset,
    parse_optional_text,
    reading_direction,
    tri_state,
)
from ..models import Project
from ..validation import KCC_CROPPINGS, KCC_ROTATIONS

INHERIT = "inherit"
ROTATION_LABELS = {0: "0 (none)", 1: "1 (90° CW)", 2: "2 (90° CCW)", 3: "3 (180°)"}
CROPPING_LABELS = {0: "0 (off)", 1: "1 (safe)", 2: "2 (aggressive)"}


def _choice_options(labels: dict[int, str], values: tuple[int, ...]) -> dict[str, str]:
    return {INHERIT: "Inherit", **{str(v): labels.get(v, str(v)) for v in values}}


class KCCForm:
    """Edit ``project.convertor`` in place; :meth:`refresh` after a kind change."""

    def __init__(
        self, project: Project, *, on_change: Callable[[], None] | None = None
    ) -> None:
        self.project = project
        self._on_change = on_change
        self._effective: dict[str, ui.label] = {}
        opts = project.convertor
        with ui.column().classes("w-full gap-2"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("menu_book")
                self.direction = (
                    ui.label().classes("text-bold").mark("reading-direction")
                )
                self.preset_label = ui.label().classes("text-grey-7")
            with ui.grid(columns=3).classes("w-full items-center gap-x-4 gap-y-1"):
                ui.label("Profile")
                ui.input(
                    value=opts.profile or "",
                    on_change=lambda e: self._set(
                        "profile", parse_optional_text(e.value)
                    ),
                ).props("dense").mark("kcc-profile")
                self._effective["profile"] = ui.label()

                for name, label in KCC_BOOL_FIELDS:
                    ui.label(label)
                    ui.toggle(
                        TRI_STATES,
                        value=tri_state(getattr(opts, name)),
                        on_change=lambda e, n=name: self._set(
                            n, from_tri_state(e.value)
                        ),
                    ).props("dense no-caps").mark(f"kcc-{name}")
                    self._effective[name] = ui.label()

                for name, labels, values in (
                    ("rotation", ROTATION_LABELS, KCC_ROTATIONS),
                    ("cropping", CROPPING_LABELS, KCC_CROPPINGS),
                ):
                    current = getattr(opts, name)
                    ui.label(name.capitalize())
                    ui.select(
                        _choice_options(labels, values),
                        value=INHERIT if current is None else str(current),
                        on_change=lambda e, n=name: self._set(
                            n, None if e.value in (None, INHERIT) else int(e.value)
                        ),
                    ).props("dense").classes("w-48").mark(f"kcc-{name}")
                    self._effective[name] = ui.label()

            ui.checkbox(
                "Force regeneration (--force-regen: rebuild existing .kepub.epub)",
                value=opts.force_regen,
                on_change=lambda e: self._set("force_regen", bool(e.value)),
            ).mark("kcc-force-regen")
        self.refresh()

    def _set(self, name: str, value: Any) -> None:
        setattr(self.project.convertor, name, value)
        self.refresh()
        if self._on_change is not None:
            self._on_change()

    def refresh(self) -> None:
        """Update the effective values (preset of the current kind + overrides)."""
        preset = kcc_preset(self.project.kind)
        effective = effective_kcc(self.project.kind, self.project.convertor)
        self.direction.text = f"Reading direction: {reading_direction(effective)}"
        self.preset_label.text = f"(preset: --preset {self.project.kind.value})"
        for name, label in self._effective.items():
            value = format_kcc_value(getattr(effective, name))
            base = format_kcc_value(getattr(preset, name))
            overridden = getattr(self.project.convertor, name) is not None
            label.text = (
                f"→ {value} (preset: {base})" if overridden else f"→ {value} (preset)"
            )
