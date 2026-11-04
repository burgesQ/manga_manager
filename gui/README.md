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
| `--data-dir` | XDG dirs | store projects and runs under `<dir>/projects` and `<dir>/runs` |
| `--loglevel` / `--verbose` | `INFO` | log level |
| `--version` | | print the version |

Data locations without `--data-dir`:

- projects: `$XDG_CONFIG_HOME/manga_manager/projects/<slug>.json` (`~/.config/...`)
- runs: `$XDG_STATE_HOME/manga_manager/runs/<slug>/<run_id>.{json,log}` (`~/.local/state/...`);
  the `.json` holds per-step argv, exit code and duration, the `.log` the full output.
  Every Dry-run / Run is recorded.

## Pages

### `/` — Projects

Lists the saved projects (name, kind, source folder) and a **New project** form (name +
source folder). Creating a project saves its profile and opens its wizard.
Duplicate / delete, last-run status and a run history page are planned (ROADMAP **G6**),
as are volume previews (**G7**).

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
| `main.py` | argparse entry point (`--host/--port/--data-dir`) → `ui.run()` |
| `models.py` | `Project`, `PackerOptions`, `KCCOptions`, `EditorOptions`, `Kind`, `slugify` |
| `commands.py` | pure `Project` → `list[StepCommand]` builder |
| `runner.py` | asyncio runner: line streaming, `parse_progress`, cancel |
| `store.py` | JSON persistence of projects and run history (XDG or `--data-dir`) |
| `validation.py` | pre-flight checks reusing the packer / editor loaders |
| `scan.py` | `.cbz` → chapter detection preview, volume folders, EPUB listing |
| `forms.py` | UI-free helpers behind the wizard (batch rows, `packer.json` / YAML edits, KCC effective values) |
| `pages/` | `projects.py` (`/`), `project.py` (`/project/<slug>` wizard) |
| `components/` | `batch_table`, `covers_grid`, `json_yaml_editor` (`FileEditor`), `kcc_form`, `log_panel` |

## Tests

```bash
uv run pytest gui -q
cd gui && uv run mypy --package manga_gui     # or: make type-check
```

UI tests drive the pages with NiceGUI's `user_simulation()` through the anyio pytest
plugin (`@pytest.mark.anyio` + the `gui_user` fixture in `tests/conftest.py`); there is
no `__init__.py` in `tests/`.
