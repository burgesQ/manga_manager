"""``/``: projects index.

MINIMAL VERSION (wave 2): a list of project links and a "New project" form
(name + source folder → save → open ``/project/{slug}``). The full Projects page
(last-run status, create from folder with auto-detection, duplicate, delete) is
planned for G6 and will extend this module.
"""

from __future__ import annotations

import logging

from nicegui import ui

from ..forms import parse_path
from ..models import Project, slugify
from ..store import Store

logger = logging.getLogger(__name__)

APP_TITLE = "manga-gui"


def create_project(store: Store, name: str, source_text: str) -> Project:
    """Create and save a new project; raises ``ValueError`` with a user message."""
    name = name.strip()
    source = parse_path(source_text)
    if not name:
        raise ValueError("project name is required")
    if source is None:
        raise ValueError("source folder is required")
    slug = slugify(name)
    if store.has_project(slug):
        raise ValueError(f"a project with slug {slug!r} already exists")
    project = Project(name=name, slug=slug, source=source)
    store.save_project(project)
    logger.info("created project %s (%s)", slug, source)
    return project


def register(store: Store) -> None:
    """Register ``/``."""

    @ui.page("/")
    def index() -> None:
        ui.label(APP_TITLE).classes("text-h4")
        projects = store.list_projects()
        ui.label(f"{len(projects)} project(s) in {store.projects_dir}").classes(
            "text-grey-7"
        )
        with ui.column().classes("gap-1"):
            for project in projects:
                with ui.row().classes("items-center gap-2"):
                    ui.link(project.name, f"/project/{project.slug}").mark(
                        f"project-link-{project.slug}"
                    )
                    ui.badge(project.kind.value).props("outline")
                    ui.label(str(project.source)).classes("text-grey-7 text-sm")

        ui.label("New project").classes("text-h6 q-mt-lg")
        with ui.row().classes("items-end gap-2"):
            name = ui.input("Name").classes("w-64").mark("new-name")
            source = ui.input("Source folder").classes("w-96").mark("new-source")

            def _create() -> None:
                try:
                    project = create_project(
                        store, str(name.value or ""), str(source.value or "")
                    )
                except (ValueError, OSError) as e:
                    ui.notify(f"Not created: {e}", type="negative")
                    return
                ui.navigate.to(f"/project/{project.slug}")

            ui.button("Create", icon="add", on_click=_create).mark("new-create")
