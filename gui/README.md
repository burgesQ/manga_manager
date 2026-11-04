# manga-gui

Local web UI ([NiceGUI](https://nicegui.io)) to set up and run the
`packer → convertor → editor` pipeline per series ("project").

**Runs on the host only.** The GUI must see your real library paths, so it is not
shipped in the Docker image (which contains the three CLIs only).

## Usage

```bash
uv sync --all-packages                # once: a plain `uv sync` does not install it
uv run manga-gui                      # http://127.0.0.1:8080
uv run manga-gui --port 9000 --data-dir ./gui-data
make gui                              # same as `uv run manga-gui`
```

| Option | Default | Purpose |
|---|---|---|
| `--host` | `127.0.0.1` | interface to bind (local only by default) |
| `--port` | `8080` | port |
| `--data-dir` | XDG dirs | store projects, runs and settings under `<dir>/projects`, `<dir>/runs`, `<dir>/settings.json` |
| `--library-root` | saved setting | library root holding the series folders (this session only, `~` expanded) |
| `--metadata-dir` | saved setting | folder of per-series files (this session only) |
| `--loglevel` / `--verbose` | `INFO` | log level |
| `--version` | | print the version |

Data locations without `--data-dir`:

- projects: `$XDG_CONFIG_HOME/manga_manager/projects/<slug>.json` (`~/.config/...`)
- runs: `$XDG_STATE_HOME/manga_manager/runs/<slug>/<run_id>.{json,log}` (`~/.local/state/...`);
  the `.json` holds per-step argv, exit code and duration, the `.log` the full output.
  Every Dry-run / Run is recorded.
- settings: `$XDG_CONFIG_HOME/manga_manager/settings.json` (`library_root`,
  `metadata_dir`), saved from the Projects page or `manga-gui import --save-settings`.

## Importing existing series: `manga-gui import`

```bash
uv run manga-gui import --library-root ~/Shelf --metadata-dir ./metadatas --dry-run
uv run manga-gui import [--library-root P] [--metadata-dir P] [--data-dir P] \
    [--dry-run] [--overwrite] [--save-settings]
```

Creates one project profile per series from two existing layouts (either one is
enough; missing flags fall back to the saved settings):

- **library root**: series folders, usually `<root>/<LANG>/<dir>/`. A folder is a
  series folder when it directly holds `.cbz` files, a `packer.json`, a `covers/` folder
  or `<Serie> vNN` volume folders. Series folders, hidden folders and git repositories
  are not descended into (depth 2 by default).
- **metadata dir**: files grouped by key: `packer_<key>.json`, `<key>.yaml` (metadata),
  `chapters_<key>.yaml`, `vols_<key>.csv` (batch).

Each group is matched to at most one series folder, strongest rule first (an exact
match always wins over a looser one): (a) the covers of `packer_<key>.json` lie inside
the folder; (b) its `serie` / the YAML `series` equals the folder's `packer.json`
`serie` or volume-folder prefix (case / punctuation-insensitive); (c) the key equals
the folder name (`fma` / `FmA`); (d) first key token = first word, other tokens = the
initials of the other words (`boruto_bv` / `BorutoBlueVortex`); (e) the folder name
starts with the key (`shangri` / `Shangri-La Frontier`).

The plan is logged as a table (status `new` / `exists` / `overwrite` / `no source`,
name, source, files, reason, issues), then applied unless `--dry-run`. A project
points to the group's `packer_<key>.json` (else the folder's `packer.json`), the
metadata YAML, the chapters YAML (unless the metadata YAML already has
`chapters_file:`), with the locale of the `<LANG>` folder (`EN` / `FR` / `JA`|`JP`,
else the locale blocks of the YAML volumes, else `english`) and the kind of the packer
config. Invalid files are reported as issues, they do not block the import. Groups
without folder are reported only. Existing slugs are skipped unless `--overwrite`.
Only profiles are written, never your files. Exit codes: `0` ok, `2` CLI error, `6`
some profiles could not be written.

## Pages

### `/` — Projects

One card per project: name, kind, source folder and a last-run chip (status, date,
dry-run flag; click it to open the history). Actions: **open**, **history**,
**duplicate** (asks for a new name) and **delete** (confirm dialog, optionally purging
the run history).

The **New project** form takes a name, a kind and a source folder. The folder is
inspected as you type: `.cbz` count, an existing `packer.json` (its `serie`, `pattern`
and `kind` prefill the project) and a `.batch` file (reported; packer picks it up on
its own). An invalid `packer.json` does not block creation: the wizard reports it.
With a library root set, a **From library** select lists its series folders
(`LANG/dir`): picking one fills the source (and the name / kind) and, when a metadata
group matches it, points the project to that group's packer config, metadata /
chapters YAML and locale.

The **Library** card holds the library root and the metadata dir (**Save** writes
`settings.json`) and an **Import…** dialog: the `manga-gui import` plan as a table
(checkbox preselected for new importable series, name, source, files, reason, issues,
an *exists* badge), an *Overwrite existing projects* switch and **Import selected**.

### `/project/<slug>/history` — run history

Runs, newest first: date, dry-run badge, duration, status and one exit-code chip per
step. Opening a run (or `?run=<id>`) shows each step's command line and the full log.
Runs can be deleted; runs of a deleted (not purged) project stay readable.

### `/project/<slug>` — wizard

A header **Save** button writes the project profile; it is also saved automatically
when you change step and before a Dry-run / Run. The steps (`ui.stepper`, free
navigation):

1. **Library** — project name, **Kind** toggle (Manga / Comic), source folder (`.cbz`
   chapters) and destination folder (volumes and `.kepub.epub`, defaults to the source).
   **Scan** lists the detected chapters with the current pattern / regexes and flags
   unmatched files, duplicate chapters (packer would abort) and chapters missing from
   the batch.
2. **Packer** — `packer.json` path, serie, pattern, workers, force, custom chapter /
   extra regexes. **Volumes** in one of three modes: single volume + chapter range,
   inline batch spec, or batch CSV file; spec and file modes are edited in a table
   (**Save batch** writes the spec or the CSV). **Covers**: one cover file per volume,
   saved into `packer.json`. **packer.json**: raw editor, validated by
   `packer.cli.load_config_file` before the file is replaced.
3. **Convertor** — KCC settings: the preset follows the project kind (`manga` /
   `comic`), every field shows the effective value and can override it.
4. **Metadata** — metadata YAML path, optional chapters YAML (`--chapters`), locale
   (`english` / `japanese` / `french`), force. A series-fields form (applied to the YAML
   editor), a volumes table (title, ISBN, release date for the locale), a read-only
   chapter-titles preview (from `--chapters`, `chapters_file:` or inline `chapters:`)
   and the raw YAML editor, the source of truth, validated by
   `editor.editor_full.load_yaml_metadata`.
5. **Review & Run** — pre-flight checks (errors block Run), a checkbox per step,
   resolved paths, the equivalent shell command of each step, then **Dry-run** (every
   enabled step with `--dry-run`), **Run** and **Cancel**, with a live log and
   progress. Steps run in order and stop at the first non-zero exit. Before packer has
   really run, a dry-run of convertor / editor has nothing to work on and reports
   nothing to do.
6. **Volumes** — one card per volume: cover thumbnail, chapter count, whether its
   `.kepub.epub` exists and, if so, the injected metadata (title, series, index, kind,
   tags, language, ISBN) read with `EPUBMetadata`. Volumes planned by the batch but not
   packed yet are shown greyed. EPUBs are read only when the step is opened, on
   Refresh and after each run (cached on path / mtime / size).

Config files are only written by their own buttons (Save file / Save batch / Save
covers), after validation. The one implicit write: switching **Kind** sets `kind` in an
existing `packer.json`.

## Design

- The real config files (`packer.json`, batch CSV, metadata / chapters YAML) remain the
  source of truth; a project only points to them and stores paths, KCC overrides,
  editor locale and enabled steps. The CLIs keep working without the GUI.
- Steps run as subprocesses (`python -m packer.main …`), never in-process, so they can
  be cancelled (SIGTERM, then SIGKILL) and their logs streamed. Each step also has an
  equivalent shell command (`StepCommand.shell()`).
- Progress is parsed from the log lines the CLIs already emit; the CLIs are unchanged.

## Modules

| Module | Role |
|---|---|
| `main.py` | argparse entry point (`--host/--port/--data-dir/--library-root/--metadata-dir`) → `ui.run()`; `import` subcommand |
| `models.py` | `Project`, `PackerOptions`, `KCCOptions`, `EditorOptions`, `Settings`, `Kind`, `slugify` |
| `discovery.py` | UI-free: series folders, metadata groups, matching, `plan_import` / `apply_import` |
| `commands.py` | pure `Project` → `list[StepCommand]` builder |
| `runner.py` | asyncio runner: line streaming, `parse_progress`, cancel |
| `store.py` | JSON persistence of projects, run history and settings (XDG or `--data-dir`) |
| `validation.py` | pre-flight checks reusing the packer / editor loaders |
| `scan.py` | `.cbz` → chapter detection preview, volume folders, EPUB listing |
| `forms.py` | UI-free helpers behind the wizard (batch rows, `packer.json` / YAML edits, KCC effective values) |
| `library.py` | UI-free project-level helpers: folder detection / prefill, create, duplicate, run summaries |
| `volumes.py` | UI-free volume previews: volume dirs, covers, EPUB metadata (cached reads) |
| `pages/` | `projects.py` (`/`), `project.py` (`/project/<slug>` wizard), `history.py` (`/project/<slug>/history`) |
| `components/` | `batch_table`, `covers_grid`, `json_yaml_editor` (`FileEditor`), `kcc_form`, `log_panel`, `previews` (`VolumePreviews`) |

## Tests

```bash
uv run pytest gui -q
cd gui && uv run mypy --package manga_gui     # or: make type-check
```

UI tests drive the pages with NiceGUI's `user_simulation()` through the anyio pytest
plugin (`@pytest.mark.anyio` + the `gui_user` fixture in `tests/conftest.py`); there is
no `__init__.py` in `tests/`.
