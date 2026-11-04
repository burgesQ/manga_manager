"""``/``: projects index.

- one card per project: name, kind, source, last run (status, date, dry-run) and
  the actions **Open**, **History**, **Duplicate** (new name → new slug, copy of the
  profile) and **Delete** (confirm dialog, optionally purging the run history);
- a **New project** form: name, kind and source folder. The folder is inspected as
  it is typed (:func:`~manga_gui.library.detect_folder`): an existing
  ``packer.json`` prefills ``packer.config`` / ``serie`` / ``pattern`` / ``kind``,
  and a batch file (``batch_file`` key or ``.batch``) is reported.

The logic lives in :mod:`manga_gui.library`; this module only builds widgets.
"""

from __future__ import annotations

import logging
from typing import Any

from nicegui import ui

from ..forms import STATUS_COLORS, parse_path
from ..library import (
    create_project,
    describe_detection,
    detect_folder,
    duplicate_project,
    last_run_summary,
)
from ..models import Kind, Project
from ..store import Store

logger = logging.getLogger(__name__)

APP_TITLE = "manga-gui"
KIND_OPTIONS = {Kind.MANGA.value: "Manga", Kind.COMIC.value: "Comic"}

__all__ = ["APP_TITLE", "create_project", "register"]


class ProjectsPage:
    """Widgets of ``/`` for one client."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self._target: Project | None = None

    def build(self) -> None:
        ui.label(APP_TITLE).classes("text-h4")
        self._build_dialogs()
        self.project_list()
        self._build_new_form()

    # -- list ---------------------------------------------------------------

    @ui.refreshable_method
    def project_list(self) -> None:
        projects = self.store.list_projects()
        ui.label(f"{len(projects)} project(s) in {self.store.projects_dir}").classes(
            "text-grey-7"
        )
        with ui.column().classes("w-full gap-2"):
            for project in projects:
                self._project_card(project)

    def _project_card(self, project: Project) -> None:
        slug = project.slug
        with ui.card().classes("w-full q-pa-sm").mark(f"project-card-{slug}"):
            with ui.row().classes("w-full items-center gap-2"):
                ui.link(project.name, f"/project/{slug}").classes("text-h6").mark(
                    f"project-link-{slug}"
                )
                ui.badge(project.kind.value).props("outline")
                ui.space()
                ui.button(
                    icon="open_in_new",
                    on_click=lambda: ui.navigate.to(f"/project/{slug}"),
                ).props("flat dense").tooltip("Open").mark(f"open-{slug}")
                ui.button(
                    icon="history",
                    on_click=lambda: ui.navigate.to(f"/project/{slug}/history"),
                ).props("flat dense").tooltip("Run history").mark(f"history-{slug}")
                ui.button(
                    icon="content_copy", on_click=lambda: self._ask_duplicate(project)
                ).props("flat dense").tooltip("Duplicate").mark(f"duplicate-{slug}")
                ui.button(
                    icon="delete",
                    color="negative",
                    on_click=lambda: self._ask_delete(project),
                ).props("flat dense").tooltip("Delete").mark(f"delete-{slug}")
            with ui.row().classes("w-full items-center gap-2"):
                ui.label(str(project.source)).classes("text-grey-7 text-sm")
                ui.space()
                self._last_run(project)

    def _last_run(self, project: Project) -> None:
        try:
            last = last_run_summary(self.store, project.slug)
        except (OSError, ValueError) as e:  # pragma: no cover - defensive
            ui.label(f"history unreadable: {e}").classes("text-negative text-sm")
            return
        marker = f"last-run-{project.slug}"
        if last is None:
            ui.label("never run").classes("text-grey-6 text-sm").mark(marker)
            return
        ui.chip(
            last.label,
            color=STATUS_COLORS[last.status],
            text_color="white",
            on_click=lambda: ui.navigate.to(f"/project/{project.slug}/history"),
        ).props("dense").mark(marker)

    # -- dialogs ------------------------------------------------------------

    def _build_dialogs(self) -> None:
        with ui.dialog() as self.duplicate_dialog, ui.card():
            self.duplicate_title = ui.label().classes("text-h6")
            self.duplicate_name = (
                ui.input("New project name").classes("w-80").mark("duplicate-name")
            )
            with ui.row():
                ui.button(
                    "Duplicate", icon="content_copy", on_click=self._duplicate
                ).mark("duplicate-confirm")
                ui.button("Cancel", on_click=self.duplicate_dialog.close).props("flat")
            self.duplicate_name.on("keydown.enter", self._duplicate)

        with ui.dialog() as self.delete_dialog, ui.card():
            self.delete_title = ui.label().classes("text-h6")
            ui.label(
                "Only the profile is deleted: the library, packer.json, batch and "
                "metadata files are kept."
            ).classes("text-grey-7")
            self.delete_purge = ui.checkbox("Also delete its run history").mark(
                "delete-purge"
            )
            with ui.row():
                ui.button(
                    "Delete", icon="delete", color="negative", on_click=self._delete
                ).mark("delete-confirm")
                ui.button("Cancel", on_click=self.delete_dialog.close).props("flat")

    def _ask_duplicate(self, project: Project) -> None:
        self._target = project
        self.duplicate_title.text = f"Duplicate {project.name}"
        self.duplicate_name.value = f"{project.name} (copy)"
        self.duplicate_dialog.open()

    def _duplicate(self) -> None:
        if self._target is None:  # pragma: no cover - dialog opened by a card
            return
        try:
            copy = duplicate_project(
                self.store, self._target.slug, str(self.duplicate_name.value or "")
            )
        except (ValueError, OSError) as e:
            ui.notify(f"Not duplicated: {e}", type="negative")
            return
        self.duplicate_dialog.close()
        ui.notify(f"Created {copy.name} ({copy.slug})", type="positive")
        self.project_list.refresh()

    def _ask_delete(self, project: Project) -> None:
        self._target = project
        self.delete_title.text = f"Delete {project.name}?"
        self.delete_purge.value = False
        self.delete_dialog.open()

    def _delete(self) -> None:
        if self._target is None:  # pragma: no cover - dialog opened by a card
            return
        purge = bool(self.delete_purge.value)
        try:
            self.store.delete_project(self._target.slug, purge_runs=purge)
        except (ValueError, OSError) as e:
            ui.notify(f"Not deleted: {e}", type="negative")
            return
        logger.info("deleted project %s (purge_runs=%s)", self._target.slug, purge)
        self.delete_dialog.close()
        ui.notify(f"Deleted {self._target.name}", type="positive")
        self.project_list.refresh()

    # -- new project --------------------------------------------------------

    def _build_new_form(self) -> None:
        ui.label("New project").classes("text-h6 q-mt-lg")
        with ui.row().classes("items-end gap-2"):
            self.new_name = ui.input("Name").classes("w-64").mark("new-name")
            self.new_source = (
                ui.input("Source folder", on_change=self._on_source)
                .classes("w-96")
                .mark("new-source")
            )
            self.new_kind = ui.toggle(KIND_OPTIONS, value=Kind.MANGA.value).mark(
                "new-kind"
            )
            ui.button("Create", icon="add", on_click=self._create).mark("new-create")
        self.detect_box = ui.column().classes("gap-0").mark("new-detection")

    def _on_source(self, e: Any) -> None:
        self.detect_box.clear()
        source = parse_path(e.value)
        if source is None:
            return
        detection = detect_folder(source)
        if detection.kind is not None:
            self.new_kind.value = detection.kind.value
        with self.detect_box:
            for line in describe_detection(detection):
                color = "text-negative" if line.startswith("Error") else "text-grey-7"
                ui.label(line).classes(f"text-sm {color}")

    def _create(self) -> None:
        try:
            project = create_project(
                self.store,
                str(self.new_name.value or ""),
                str(self.new_source.value or ""),
                kind=Kind(self.new_kind.value or Kind.MANGA.value),
            )
        except (ValueError, OSError) as e:
            ui.notify(f"Not created: {e}", type="negative")
            return
        ui.navigate.to(f"/project/{project.slug}")


def register(store: Store) -> None:
    """Register ``/``."""

    @ui.page("/")
    def index() -> None:
        ProjectsPage(store).build()
