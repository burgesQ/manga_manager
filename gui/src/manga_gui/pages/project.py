"""``/project/{slug}``: the 5-step wizard (Library → Packer → Convertor → Metadata
→ Review & Run).

Saving model
------------
- The **project profile** (``Store``) is edited in memory by every form field and
  written by the header **Save** button, automatically whenever the user moves to
  another step of the stepper, and right before a Dry-run / Run.
- The **real config files** (``packer.json``, batch CSV, metadata YAML) are only
  written by their own explicit buttons ("Save file", "Save to batch file",
  "Save covers"), after validation by the CLI loaders. The one implicit write is
  the Kind toggle, which sets ``kind`` in an existing ``packer.json``.
"""

from __future__ import annotations

import logging
from typing import Any

from nicegui import background_tasks, context, ui

from packer.core import NAMED_PATTERNS

from ..commands import StepCommand, build_commands
from ..components.batch_table import BatchTable
from ..components.covers_grid import CoversGrid
from ..components.json_yaml_editor import FileEditor
from ..components.kcc_form import KCCForm
from ..components.log_panel import LogPanel
from ..forms import (
    METADATA_TEMPLATE,
    PACKER_JSON_TEMPLATE,
    SERIES_FIELDS,
    VOLUME_MODES,
    StepStatus,
    VolumeMode,
    apply_series_fields,
    batch_rows_from_spec,
    batch_rows_to_spec,
    chapter_titles,
    cover_rows,
    display_path,
    dump_yaml,
    effective_batch_file,
    packer_json_covers,
    parse_metadata_text,
    parse_optional_text,
    parse_path,
    read_batch_file,
    save_metadata_text,
    save_packer_json_text,
    scan_rows,
    series_fields,
    set_packer_json_covers,
    set_packer_json_kind,
    step_status,
    switch_volume_mode,
    volume_mode,
    volume_rows,
    write_batch_file,
)
from ..models import LOCALES, STEP_NAMES, Kind, Project
from ..runner import PipelineResult, PipelineRunner, StepResult
from ..scan import scan_library
from ..store import Store
from ..validation import (
    config_path_for,
    has_errors,
    resolve_batch_specs,
    resolve_packer_settings,
    validate_project,
)

logger = logging.getLogger(__name__)

KIND_OPTIONS = {Kind.MANGA.value: "Manga", Kind.COMIC.value: "Comic"}
PATTERN_OPTIONS = ["default", *NAMED_PATTERNS]
STEP_LABELS = {
    "library": "Library",
    "packer": "Packer",
    "convertor": "Convertor",
    "metadata": "Metadata",
    "review": "Review & Run",
}
DRY_RUN_NOTE = (
    "Dry-run runs every enabled step with --dry-run. Convertor and editor only "
    "see the volumes / EPUBs that already exist in the destination, so before a "
    "real packer run they report nothing to do."
)


def _section(title: str) -> None:
    ui.label(title).classes("text-subtitle1 text-bold q-mt-md")


class ProjectPage:
    """State and widgets of one opened project page (one instance per client)."""

    def __init__(self, store: Store, project: Project) -> None:
        self.store = store
        self.project = project
        self.client = context.client
        self.runner = PipelineRunner()
        self._busy = False
        self._has_errors = True
        self._volume_stash: dict[str, Any] = {}
        self._mode_boxes: dict[str, ui.element] = {}
        # widgets created by build()
        self.packer_editor: FileEditor
        self.metadata_editor: FileEditor
        self.kcc_form: KCCForm

    # -- layout -------------------------------------------------------------

    def build(self) -> None:
        with ui.row().classes("w-full items-center"):
            ui.link("← Projects", "/")
            self.title = ui.label(self.project.name).classes("text-h5")
            ui.space()
            ui.button("Save", icon="save", on_click=lambda: self.save()).mark(
                "save-project"
            )
        with (
            ui.stepper(on_value_change=self._on_step_change)
            .props("header-nav animated")
            .classes("w-full") as self.stepper
        ):
            with ui.step("library", title=STEP_LABELS["library"]):
                self._build_library()
                self._nav(first=True)
            with ui.step("packer", title=STEP_LABELS["packer"]):
                self._build_packer()
                self._nav()
            with ui.step("convertor", title=STEP_LABELS["convertor"]):
                self.kcc_form = KCCForm(self.project, on_change=self._refresh_review)
                self._nav()
            with ui.step("metadata", title=STEP_LABELS["metadata"]):
                self._build_metadata()
                self._nav()
            with ui.step("review", title=STEP_LABELS["review"]):
                self._build_review()
                self._nav(last=True)
        self.packer_editor.load()
        self.metadata_editor.load()
        self._load_batch_table()
        self._refresh_review()

    def _nav(self, *, first: bool = False, last: bool = False) -> None:
        with ui.stepper_navigation():
            if not last:
                ui.button("Next", on_click=self.stepper.next)
            if not first:
                ui.button("Back", on_click=self.stepper.previous).props("flat")

    def _on_step_change(self, e: Any) -> None:
        self.save(quiet=True)
        if e.value == "review":
            self._refresh_review()

    # -- persistence --------------------------------------------------------

    def save(self, *, quiet: bool = False) -> None:
        """Write the project profile; report validation unless ``quiet``."""
        try:
            self.store.save_project(self.project)
        except (OSError, ValueError) as e:
            ui.notify(f"Project not saved: {e}", type="negative")
            return
        if quiet:
            return
        issues = validate_project(self.project)
        errors = sum(1 for i in issues if i.level == "error")
        warnings = len(issues) - errors
        if errors:
            ui.notify(
                f"Project saved — {errors} error(s), {warnings} warning(s): "
                "see Review & Run",
                type="warning",
            )
        else:
            ui.notify(f"Project saved — {warnings} warning(s)", type="positive")

    # -- step 1: library ----------------------------------------------------

    def _build_library(self) -> None:
        p = self.project
        with ui.column().classes("w-full gap-2"):
            ui.input(
                "Project name",
                value=p.name,
                on_change=self._on_name,
                validation={"Required": lambda v: bool(v and v.strip())},
            ).classes("w-96").mark("project-name")
            with ui.row().classes("items-center gap-2"):
                ui.label("Kind")
                ui.toggle(
                    KIND_OPTIONS, value=p.kind.value, on_change=self._on_kind
                ).mark("kind-toggle")
            ui.input(
                "Source folder (.cbz chapters)",
                value=display_path(p.source),
                on_change=self._on_source,
                validation={"Required": lambda v: bool(v and v.strip())},
            ).classes("w-full").mark("source")
            self.dest_input = (
                ui.input(
                    "Destination folder (volumes, .kepub.epub)",
                    value=display_path(p.dest),
                    placeholder=display_path(p.source),
                    on_change=lambda e: self._set_dest(e.value),
                )
                .classes("w-full")
                .mark("dest")
            )
            ui.button("Scan", icon="search", on_click=self._scan).mark("scan")
            self.scan_box = ui.column().classes("w-full gap-1")

    def _on_name(self, e: Any) -> None:
        if e.value and e.value.strip():
            self.project.name = e.value.strip()
            self.title.text = self.project.name

    def _on_source(self, e: Any) -> None:
        source = parse_path(e.value)
        if source is not None:
            self.project.source = source
            self.dest_input.props["placeholder"] = str(source)

    def _set_dest(self, value: str | None) -> None:
        self.project.dest = parse_path(value)

    def _on_kind(self, e: Any) -> None:
        kind = Kind(e.value)
        if kind == self.project.kind:
            return
        self.project.kind = kind
        cfg = config_path_for(self.project)
        try:
            if set_packer_json_kind(cfg, kind):
                ui.notify(f"kind: {kind.value} written to {cfg}")
                self.packer_editor.load()
        except (ValueError, OSError) as err:
            ui.notify(f"packer.json not updated: {err}", type="warning")
        self.kcc_form.refresh()
        self._refresh_review()

    def _scan(self) -> None:
        result = scan_library(self.project)
        self.scan_box.clear()
        with self.scan_box:
            for err in result.errors:
                ui.label(f"Error: {err}").classes("text-negative")
            ui.label(
                f"{len(result.chapters)} chapter file(s) detected, "
                f"{len(result.unmatched)} unmatched"
            ).mark("scan-summary")
            if result.duplicates:
                dupes = ", ".join(str(n) for n in result.duplicates)
                ui.label(f"Duplicate chapters (packer aborts): {dupes}").classes(
                    "text-negative"
                )
            if result.missing:
                missing = ", ".join(str(n) for n in result.missing)
                ui.label(f"Missing chapters of the batch: {missing}").classes(
                    "text-warning"
                )
            for f in result.unmatched:
                ui.label(f"Unmatched: {f.name}").classes("text-negative")
            ui.table(
                columns=[
                    {"name": "number", "label": "Chapter", "field": "number"},
                    {"name": "extra", "label": "Extra", "field": "extra"},
                    {"name": "file", "label": "File", "field": "file", "align": "left"},
                ],
                rows=scan_rows(result),
                row_key="file",
                pagination=50,
            ).classes("w-full").props("dense flat").mark("scan-table")

    # -- step 2: packer -----------------------------------------------------

    def _build_packer(self) -> None:
        opts = self.project.packer
        with ui.column().classes("w-full gap-2"):
            ui.input(
                "packer.json path",
                value=display_path(opts.config),
                placeholder=str(self.project.source / "packer.json"),
                on_change=lambda e: setattr(opts, "config", parse_path(e.value)),
            ).classes("w-full").mark("packer-config")
            with ui.row().classes("w-full gap-4"):
                ui.input(
                    "Serie",
                    value=opts.serie or "",
                    on_change=lambda e: setattr(
                        opts, "serie", parse_optional_text(e.value)
                    ),
                ).classes("w-64").mark("packer-serie")
                ui.select(
                    PATTERN_OPTIONS,
                    label="Pattern",
                    value=(
                        opts.pattern if opts.pattern in PATTERN_OPTIONS else "default"
                    ),
                    on_change=lambda e: setattr(opts, "pattern", e.value or "default"),
                ).classes("w-48").mark("packer-pattern")
                ui.number(
                    "Workers",
                    value=opts.nb_worker,
                    min=1,
                    precision=0,
                    on_change=lambda e: setattr(
                        opts, "nb_worker", max(1, int(e.value or 1))
                    ),
                ).classes("w-24")
                ui.checkbox(
                    "Force (overwrite)",
                    value=opts.force,
                    on_change=lambda e: setattr(opts, "force", bool(e.value)),
                )
            with ui.row().classes("w-full gap-4"):
                ui.input(
                    "Chapter regex (1 group)",
                    value=opts.chapter_regex or "",
                    on_change=lambda e: setattr(
                        opts, "chapter_regex", parse_optional_text(e.value)
                    ),
                ).classes("w-96")
                ui.input(
                    "Extra regex (2 groups)",
                    value=opts.extra_regex or "",
                    on_change=lambda e: setattr(
                        opts, "extra_regex", parse_optional_text(e.value)
                    ),
                ).classes("w-96")

            _section("Volumes")
            self.mode_toggle = ui.toggle(
                VOLUME_MODES, value=volume_mode(opts), on_change=self._on_volume_mode
            ).mark("volume-mode")
            with ui.column().classes("w-full") as self._mode_boxes["spec"]:
                self.batch_spec_input = (
                    ui.input(
                        "Batch spec (v01:1..3-v02:4..6)",
                        value=opts.batch or "",
                        on_change=lambda e: setattr(
                            opts, "batch", parse_optional_text(e.value)
                        ),
                    )
                    .classes("w-full")
                    .mark("batch-spec")
                )
            with ui.column().classes("w-full") as self._mode_boxes["file"]:
                self.batch_file_input = (
                    ui.input(
                        "Batch file (CSV: vNN,range)",
                        value=display_path(opts.batch_file),
                        on_change=self._on_batch_file,
                    )
                    .classes("w-full")
                    .mark("batch-file")
                )
            with ui.row().classes("w-full gap-4") as self._mode_boxes["single"]:
                ui.number(
                    "Volume",
                    value=opts.volume,
                    min=0,
                    precision=0,
                    on_change=lambda e: setattr(
                        opts, "volume", None if e.value is None else int(e.value)
                    ),
                ).classes("w-24").mark("single-volume")
                ui.input(
                    "Chapter range (1..12, 1,3,5..8)",
                    value=opts.chapter_range or "",
                    on_change=lambda e: setattr(
                        opts, "chapter_range", parse_optional_text(e.value)
                    ),
                ).classes("w-64").mark("single-range")
            with ui.column().classes("w-full gap-1") as self.batch_box:
                self.batch_target = ui.label().classes("text-caption text-grey-7")
                self.batch_table = BatchTable()
                with ui.row():
                    ui.button(
                        "Load", icon="refresh", on_click=self._load_batch_table
                    ).props("flat")
                    ui.button(
                        "Save batch", icon="save", on_click=self._save_batch_table
                    ).mark("batch-save")
            self._show_mode(volume_mode(opts))

            _section("Covers")
            self.covers = CoversGrid(on_save=self._save_covers)

            _section("packer.json")
            self.packer_editor = FileEditor(
                language="JSON",
                get_path=lambda: config_path_for(self.project),
                save=save_packer_json_text,
                template=PACKER_JSON_TEMPLATE,
                marker="packer-json",
                on_saved=lambda _text: self._refresh_covers(),
            )

    def _on_batch_file(self, e: Any) -> None:
        self.project.packer.batch_file = parse_path(e.value)
        self._update_batch_target()

    def _on_volume_mode(self, e: Any) -> None:
        mode: VolumeMode = e.value if e.value in VOLUME_MODES else "file"
        switch_volume_mode(self.project.packer, mode, self._volume_stash)
        self._show_mode(mode)
        self._load_batch_table()

    def _show_mode(self, mode: str) -> None:
        for name, box in self._mode_boxes.items():
            box.set_visibility(name == mode)
        self.batch_box.set_visibility(mode in ("spec", "file"))
        self._update_batch_target()

    def _update_batch_target(self) -> None:
        if self.mode_toggle.value == "spec":
            self.batch_target.text = "Saving writes the batch spec above"
        else:
            target = effective_batch_file(self.project)
            self.batch_target.text = f"Saving writes {target}"
            self.batch_file_input.props["placeholder"] = str(target)

    def _load_batch_table(self) -> None:
        mode = self.mode_toggle.value
        try:
            if mode == "spec":
                rows = batch_rows_from_spec(self.project.packer.batch)
            else:
                rows = read_batch_file(effective_batch_file(self.project))
        except (ValueError, OSError) as e:
            ui.notify(f"Cannot read the batch: {e}", type="negative")
            rows = []
        self.batch_table.set_rows(rows)
        self._update_batch_target()
        self._refresh_covers()

    def _save_batch_table(self) -> None:
        try:
            rows = self.batch_table.rows()
            if self.mode_toggle.value == "spec":
                spec = batch_rows_to_spec(rows)
                self.batch_spec_input.value = spec
                self.project.packer.batch = spec or None
                ui.notify("Batch spec updated", type="positive")
            else:
                target = effective_batch_file(self.project)
                write_batch_file(target, rows)
                ui.notify(f"Saved {target}", type="positive")
        except (ValueError, OSError) as e:
            ui.notify(f"Batch not saved: {e}", type="negative")
            return
        self._refresh_covers()

    def _batch_volumes(self) -> list[int]:
        volumes = self.batch_table.volumes()
        if volumes or self.mode_toggle.value != "single":
            return volumes
        try:
            specs = resolve_batch_specs(
                resolve_packer_settings(self.project), self.project.source
            )
        except (ValueError, OSError):
            return []
        return [vol for vol, _ in specs]

    def _refresh_covers(self) -> None:
        cfg = config_path_for(self.project)
        self.covers.set_rows(
            cfg, cover_rows(cfg, self._batch_volumes(), packer_json_covers(cfg))
        )

    def _save_covers(self, covers: dict[int, str]) -> None:
        cfg = config_path_for(self.project)
        try:
            set_packer_json_covers(cfg, covers)
        except (ValueError, OSError) as e:
            ui.notify(f"Covers not saved: {e}", type="negative")
            return
        ui.notify(f"Covers saved to {cfg}", type="positive")
        self.packer_editor.load()
        self._refresh_covers()

    # -- step 4: metadata ---------------------------------------------------

    def _build_metadata(self) -> None:
        opts = self.project.editor
        with ui.column().classes("w-full gap-2"):
            with ui.row().classes("w-full gap-4"):
                ui.input(
                    "Metadata YAML",
                    value=display_path(opts.metadata),
                    on_change=lambda e: setattr(opts, "metadata", parse_path(e.value)),
                ).classes("w-96").mark("metadata-path")
                ui.input(
                    "Chapters YAML (--chapters, optional)",
                    value=display_path(opts.chapters),
                    on_change=lambda e: setattr(opts, "chapters", parse_path(e.value)),
                ).classes("w-96").mark("chapters-path")
                ui.select(
                    list(LOCALES),
                    label="Locale",
                    value=opts.locale,
                    on_change=self._on_locale,
                ).classes("w-40")
                ui.checkbox(
                    "Force (overwrite existing metadata)",
                    value=opts.force,
                    on_change=lambda e: setattr(opts, "force", bool(e.value)),
                )

            _section("Series")
            self.series_inputs: dict[str, ui.input] = {}
            with ui.row().classes("w-full gap-4"):
                for key in SERIES_FIELDS:
                    self.series_inputs[key] = (
                        ui.input(key.capitalize()).classes("w-56").mark(f"meta-{key}")
                    )
            with ui.row():
                ui.button(
                    "Apply to YAML editor", icon="edit", on_click=self._apply_series
                ).props("flat")
                ui.button(
                    "Refresh from editor",
                    icon="refresh",
                    on_click=lambda: self._refresh_metadata_preview(
                        self.metadata_editor.text
                    ),
                ).props("flat")
            self.metadata_error = ui.label().classes("text-negative")

            _section("Volumes")
            self.volumes_table = (
                ui.table(
                    columns=[
                        {"name": "number", "label": "Vol.", "field": "number"},
                        {"name": "title", "label": "Title", "field": "title"},
                        {"name": "isbn", "label": "ISBN", "field": "isbn"},
                        {
                            "name": "release_date",
                            "label": "Release",
                            "field": "release_date",
                        },
                    ],
                    rows=[],
                    row_key="number",
                    pagination=25,
                )
                .classes("w-full")
                .props("dense flat")
                .mark("volumes-table")
            )

            _section("Chapter titles (read-only)")
            self.chapters_source = ui.label().classes("text-caption text-grey-7")
            self.chapters_table = (
                ui.table(
                    columns=[
                        {"name": "number", "label": "Chapter", "field": "number"},
                        {
                            "name": "title",
                            "label": "Title",
                            "field": "title",
                            "align": "left",
                        },
                    ],
                    rows=[],
                    row_key="number",
                    pagination=25,
                )
                .classes("w-full")
                .props("dense flat")
                .mark("chapters-table")
            )

            _section("Metadata YAML (source of truth)")
            self.metadata_editor = FileEditor(
                language="YAML",
                get_path=lambda: self.project.editor.metadata,
                save=save_metadata_text,
                template=METADATA_TEMPLATE,
                marker="metadata",
                on_loaded=self._refresh_metadata_preview,
                on_saved=self._refresh_metadata_preview,
            )

    def _on_locale(self, e: Any) -> None:
        self.project.editor.locale = e.value or "english"
        self._refresh_metadata_preview(self.metadata_editor.text)

    def _refresh_metadata_preview(self, text: str) -> None:
        locale = self.project.editor.locale
        try:
            data = parse_metadata_text(text)
        except ValueError as e:
            self.metadata_error.text = str(e)
            return
        self.metadata_error.text = ""
        for key, value in series_fields(data, locale).items():
            self.series_inputs[key].value = value
        self.volumes_table.rows = [r._asdict() for r in volume_rows(data, locale)]
        titles = chapter_titles(
            data, self.project.editor.metadata, self.project.editor.chapters
        )
        self.chapters_source.text = f"Source: {titles.source}" + (
            f" — {titles.error}" if titles.error else ""
        )
        self.chapters_table.rows = [
            {"number": n, "title": t} for n, t in titles.titles.items()
        ]

    def _apply_series(self) -> None:
        locale = self.project.editor.locale
        try:
            data = parse_metadata_text(self.metadata_editor.text)
        except ValueError as e:
            ui.notify(f"Fix the YAML first: {e}", type="negative")
            return
        fields = {k: str(i.value or "") for k, i in self.series_inputs.items()}
        new_data = apply_series_fields(data, fields, locale)
        if new_data == data:
            ui.notify("Nothing changed")
            return
        self.metadata_editor.text = dump_yaml(new_data)
        self._refresh_metadata_preview(self.metadata_editor.text)
        ui.notify(
            "YAML editor updated (comments are not kept): click Save file to write it",
            type="info",
        )

    # -- step 5: review & run -----------------------------------------------

    def _build_review(self) -> None:
        with ui.column().classes("w-full gap-2"):
            self.review_box = ui.column().classes("w-full gap-2").mark("review")
            ui.label(DRY_RUN_NOTE).classes("text-caption text-grey-7")
            with ui.row().classes("gap-2"):
                self.dry_run_button = ui.button(
                    "Dry-run",
                    icon="visibility",
                    on_click=lambda: self.start(dry_run=True),
                ).mark("dry-run")
                self.run_button = ui.button(
                    "Run",
                    icon="play_arrow",
                    color="positive",
                    on_click=lambda: self.start(dry_run=False),
                ).mark("run")
                self.cancel_button = ui.button(
                    "Cancel", icon="stop", color="negative", on_click=self.cancel
                ).mark("cancel")
            self.log_panel = LogPanel()
        self._update_buttons()

    def _refresh_review(self) -> None:
        """Rebuild issues, step checkboxes, resolved paths and commands."""
        p = self.project
        issues = validate_project(p)
        self._has_errors = has_errors(issues)
        self.review_box.clear()
        with self.review_box:
            _section("Checks")
            if not issues:
                ui.label("No issue found").classes("text-positive")
            for issue in issues:
                color = "text-negative" if issue.level == "error" else "text-warning"
                ui.label(f"[{issue.level}] {issue.step}: {issue.message}").classes(
                    color
                ).mark(f"issue-{issue.level}")

            _section("Steps")
            with ui.row():
                for step in STEP_NAMES:
                    ui.checkbox(
                        step,
                        value=p.step_enabled(step),
                        on_change=lambda e, s=step: self._toggle_step(s, e.value),
                    ).mark(f"step-{step}")

            _section("Paths")
            for label, path in self._resolved_paths():
                ui.label(f"{label}: {path}").classes("font-mono text-sm")

            _section("Commands")
            commands = build_commands(p)
            if not commands:
                ui.label("No step enabled").classes("text-grey-7")
            for cmd in commands:
                self._command_block(cmd)
        self._update_buttons()

    def _command_block(self, cmd: StepCommand) -> None:
        ui.code(cmd.shell(), language="bash").classes("w-full").mark(
            f"command-{cmd.step}"
        )

    def _resolved_paths(self) -> list[tuple[str, str]]:
        p = self.project
        paths = [
            ("Source", str(p.source)),
            ("Destination", str(p.effective_dest)),
            ("packer.json", str(config_path_for(p))),
        ]
        try:
            settings = resolve_packer_settings(p)
            batch_file = settings.batch_file
        except ValueError:
            batch_file = p.packer.batch_file
        if p.packer.batch:
            paths.append(("Batch", p.packer.batch))
        elif batch_file is not None:
            paths.append(("Batch file", str(batch_file)))
        paths.append(("Metadata YAML", display_path(p.editor.metadata) or "—"))
        paths.append(("Chapters YAML", display_path(p.editor.chapters) or "—"))
        return paths

    def _toggle_step(self, step: str, value: Any) -> None:
        self.project.steps[step] = bool(value)
        self._refresh_review()

    def _update_buttons(self) -> None:
        busy = self._busy
        self.dry_run_button.set_enabled(not busy)
        self.run_button.set_enabled(not busy and not self._has_errors)
        self.cancel_button.set_enabled(busy)

    # -- running ------------------------------------------------------------

    def start(self, *, dry_run: bool) -> None:
        """Validate, then run the enabled steps in a background task."""
        if self._busy:
            ui.notify("A run is already in progress", type="warning")
            return
        self.save(quiet=True)
        self._refresh_review()
        if not dry_run and self._has_errors:
            ui.notify("Fix the errors listed in Checks first", type="negative")
            return
        commands = build_commands(self.project, dry_run=dry_run)
        if not commands:
            ui.notify("No step to run", type="warning")
            return
        self.log_panel.reset([c.step for c in commands])
        self._busy = True
        self._update_buttons()
        background_tasks.create(
            self._run(commands, dry_run=dry_run), name=f"run-{self.project.slug}"
        )

    def cancel(self) -> None:
        self.runner.cancel()
        ui.notify("Cancelling…")

    async def _run(self, commands: list[StepCommand], *, dry_run: bool) -> None:
        try:
            result = await self.runner.run(
                commands,
                self._on_line,
                self._on_step_start,
                self._on_step_end,
                dry_run=dry_run,
            )
        except Exception:  # pragma: no cover - defensive: runner errors
            logger.exception("pipeline run failed")
            self._busy = False  # before the button refresh below
            self._ui(self._update_buttons)
            self._ui(lambda: ui.notify("Run failed", type="negative"))
            return
        finally:
            self._busy = False
        record = self.store.save_run(self.project.slug, result, self.log_panel.text())
        logger.info("run %s saved (exit code %s)", record.run_id, result.exit_code)
        self._ui(lambda: self._finish(result))

    def _finish(self, result: PipelineResult) -> None:
        if result.cancelled:
            self.log_panel.mark_pending_as(StepStatus.CANCELLED)
        self._update_buttons()
        kind = "Dry-run" if result.dry_run else "Run"
        if result.ok:
            ui.notify(f"{kind} finished", type="positive")
        elif result.cancelled:
            ui.notify(f"{kind} cancelled", type="warning")
        else:
            ui.notify(f"{kind} failed (exit code {result.exit_code})", type="negative")

    def _ui(self, fn: Any) -> None:
        """Run a UI update from the background task, if the page is still open."""
        if not self.log_panel.alive:
            return
        with self.client:
            fn()

    def _on_line(self, line: str) -> None:
        self._ui(lambda: self.log_panel.push(line))

    def _on_step_start(self, cmd: StepCommand) -> None:
        self._ui(lambda: self.log_panel.set_status(cmd.step, StepStatus.RUNNING))
        self._ui(lambda: self.log_panel.push(f"$ {cmd.shell()}"))

    def _on_step_end(self, result: StepResult) -> None:
        self._ui(lambda: self.log_panel.set_status(result.step, step_status(result)))


def _not_found(slug: str, reason: str) -> None:
    ui.label(f"Project not found: {slug}").classes("text-h5")
    ui.label(reason).classes("text-grey-7")
    ui.link("← Projects", "/")


def register(store: Store) -> None:
    """Register ``/project/{slug}``."""

    @ui.page("/project/{slug}")
    def project_page(slug: str) -> None:
        try:
            project = store.load_project(slug)
        except FileNotFoundError:
            _not_found(slug, "no such project")
            return
        except (OSError, ValueError, KeyError, TypeError) as e:
            _not_found(slug, str(e))
            return
        ProjectPage(store, project).build()
