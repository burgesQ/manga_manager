"""``/project/{slug}/history``: stored runs of a project.

Left: the runs, newest first (start date, dry-run flag, duration, overall status
and one chip per step with its exit code). Clicking a run's date shows its detail on the
right: the argv of every step and the full log, read-only. A run can be deleted
(confirm dialog). ``?run=<run_id>`` opens a run directly.

The history stays reachable after the project profile was deleted without purging
its runs, so orphaned runs can still be read and cleaned up.
"""

from __future__ import annotations

import logging
import shlex

from nicegui import ui

from ..forms import STATUS_COLORS
from ..library import RunSummary, format_duration, format_started_at, run_summaries
from ..store import Store

logger = logging.getLogger(__name__)


class HistoryPage:
    """Widgets of one history page (one instance per client)."""

    def __init__(self, store: Store, slug: str, name: str) -> None:
        self.store = store
        self.slug = slug
        self.name = name
        self._runs: dict[str, RunSummary] = {}
        self._selected: str | None = None
        self._to_delete: str | None = None

    def build(self, run_id: str | None = None) -> None:
        with ui.row().classes("w-full items-center"):
            ui.link("← Projects", "/")
            ui.link("Project", f"/project/{self.slug}").mark("project-link")
            ui.label(f"Run history — {self.name}").classes("text-h5")
        with ui.dialog() as self.delete_dialog, ui.card():
            self.delete_title = ui.label().classes("text-h6")
            with ui.row():
                ui.button(
                    "Delete", icon="delete", color="negative", on_click=self._delete
                ).mark("run-delete-confirm")
                ui.button("Cancel", on_click=self.delete_dialog.close).props("flat")
        with ui.row().classes("w-full no-wrap items-start gap-4"):
            self.list_box = ui.column().classes("w-1/3 min-w-80 gap-2")
            self.detail_box = ui.column().classes("w-2/3 gap-2").mark("run-detail")
        self.refresh()
        if run_id in self._runs:
            self.show(run_id)

    # -- list ---------------------------------------------------------------

    def refresh(self) -> None:
        """Reload the run list from the store."""
        self._runs = {r.run_id: r for r in run_summaries(self.store, self.slug)}
        self.list_box.clear()
        with self.list_box:
            ui.label(f"{len(self._runs)} run(s)").classes("text-grey-7").mark(
                "run-count"
            )
            for run in self._runs.values():
                self._run_card(run)
        if self._selected not in self._runs:
            self._selected = None
            self.detail_box.clear()
            with self.detail_box:
                ui.label("Select a run to see its commands and log").classes(
                    "text-grey-7"
                )

    def _run_card(self, run: RunSummary) -> None:
        with ui.card().classes("w-full q-pa-sm").mark(f"run-{run.run_id}"):
            with ui.row().classes("w-full items-center gap-2"):
                ui.button(
                    format_started_at(run.started_at),
                    icon="article",
                    on_click=lambda r=run.run_id: self.show(r),
                ).props("flat dense no-caps").tooltip("Show commands and log").mark(
                    f"run-open-{run.run_id}"
                )
                if run.dry_run:
                    ui.badge("dry-run", color="grey").props("outline")
                ui.space()
                ui.chip(
                    run.status.value,
                    color=STATUS_COLORS[run.status],
                    text_color="white",
                ).props("dense").mark(f"run-status-{run.run_id}")
            with ui.row().classes("w-full items-center gap-1"):
                ui.label(format_duration(run.duration)).classes("text-grey-7 text-sm")
                for step in run.steps:
                    ui.chip(
                        f"{step.step}: {step.exit_code}",
                        color=STATUS_COLORS[step.status],
                        text_color="white",
                    ).props("dense outline")
                if not run.steps:
                    ui.label("no step started").classes("text-grey-6 text-sm")
                ui.space()
                ui.button(
                    icon="delete",
                    color="negative",
                    on_click=lambda r=run.run_id: self._ask_delete(r),
                ).props("flat dense").tooltip("Delete this run").mark(
                    f"run-delete-{run.run_id}"
                )

    # -- detail -------------------------------------------------------------

    def show(self, run_id: str) -> None:
        """Show the commands and log of ``run_id``."""
        run = self._runs.get(run_id)
        if run is None:  # pragma: no cover - cards only exist for known runs
            return
        self._selected = run_id
        try:
            log_text = self.store.read_run_log(self.slug, run_id)
        except (OSError, ValueError) as e:  # pragma: no cover - defensive
            log_text = f"(log unreadable: {e})"
        self.detail_box.clear()
        with self.detail_box:
            mode = "Dry-run" if run.dry_run else "Run"
            ui.label(
                f"{mode} of {format_started_at(run.started_at)} — {run.status.value}"
                f" (exit code {run.exit_code}, {format_duration(run.duration)})"
            ).classes("text-h6")
            for step in run.steps:
                ui.label(
                    f"{step.step}: exit code {step.exit_code}, "
                    f"{format_duration(step.duration)}"
                ).classes("text-subtitle2")
                ui.code(shlex.join(step.argv), language="bash").classes("w-full").mark(
                    f"run-argv-{step.step}"
                )
            ui.label("Log").classes("text-subtitle1 text-bold q-mt-md")
            log = ui.log().classes("w-full h-96 font-mono text-xs").mark("history-log")
            if log_text:
                log.push(log_text.rstrip("\n"))
            else:
                ui.label("(empty log)").classes("text-grey-7")

    # -- delete -------------------------------------------------------------

    def _ask_delete(self, run_id: str) -> None:
        run = self._runs.get(run_id)
        if run is None:  # pragma: no cover - cards only exist for known runs
            return
        self._to_delete = run_id
        self.delete_title.text = (
            f"Delete the run of {format_started_at(run.started_at)}?"
        )
        self.delete_dialog.open()

    def _delete(self) -> None:
        run_id = self._to_delete
        if run_id is None:  # pragma: no cover - dialog opened by a card
            return
        try:
            self.store.delete_run(self.slug, run_id)
        except (OSError, ValueError) as e:
            ui.notify(f"Run not deleted: {e}", type="negative")
            return
        logger.info("deleted run %s of %s", run_id, self.slug)
        self._to_delete = None
        self.delete_dialog.close()
        ui.notify("Run deleted", type="positive")
        self.refresh()


def register(store: Store) -> None:
    """Register ``/project/{slug}/history``."""

    @ui.page("/project/{slug}/history")
    def history_page(slug: str, run: str | None = None) -> None:
        try:
            store.project_path(slug)  # validates the slug
        except ValueError as e:
            ui.label(f"Invalid project: {e}").classes("text-h5")
            ui.link("← Projects", "/")
            return
        try:
            name = store.load_project(slug).name
        except (OSError, ValueError, KeyError, TypeError):
            name = slug
            ui.label(f"Project {slug!r} not found: showing its remaining runs").classes(
                "text-warning"
            )
        HistoryPage(store, slug, name).build(run)
