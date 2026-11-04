# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`manga_manager` is a Python 3.12+ monorepo (uv workspace) of three CLI tools, plus a local web UI, to manage manga (and comic) libraries targeting Kobo e-readers.

**Full workflow:**
```
*.cbz archives → packer → volume dirs → convertor → *.kepub.epub → editor (metadata) → Kobo
```

**Packages:**
| Package | Version | Purpose |
|---|---|---|
| `packer` | v0.1.0 | Group `.cbz` chapter archives into volume directories with extracted chapter subdirs |
| `convertor` | v1.0 | Convert volume directories to `.kepub.epub` via KindleComicConverter (KCC); `--preset manga\|comic` |
| `editor` | v1.0 | Inject / dump / clear EPUB metadata from YAML files |
| `gui` (`manga-gui`, package `manga_gui`) | v0.1.0 | NiceGUI web UI: per-series projects, config editors, runs packer → convertor → editor as subprocesses. **Host only**, not in the Docker image |

- **Language:** Python 3.12+ — `packer` uses stdlib only, no external deps
- **Package manager:** `uv` workspace (see root `pyproject.toml`). Always `uv sync --all-packages`: the root project is a bare container, so a plain `uv sync` does not install (and removes) the workspace members and nicegui
- **Docker image:** CLI-only — installs `--package packer --package editor --package convertor`; `gui/` sources are excluded via `.dockerignore` (only `gui/pyproject.toml` is copied so uv can resolve the workspace)
- **Platform:** Linux (tested on Linux Mint 22.3 / Debian 13)

---

## Architecture

### packer

Reads `.cbz` archives from `--path`, matches chapter numbers via regex patterns, creates a volume directory (`[Serie] vNN`), moves archives in, and extracts each into a `Chapter NNN/` subdirectory.

```
src/packer/
├── cli.py        # argparse CLI + orchestration (_build_parser, _apply_path_config,
│                 #   _validate_args, _compile_patterns, _resolve_batch_specs, _run_batch)
├── core.py       # file discovery, regex parsing, NAMED_PATTERNS dict
├── worker.py     # per-chapter processing (_plan_tasks, _copy_cover, _run_tasks,
│                 #   process_one, process_volume)
├── config.py     # Config dataclass — single object passed through the call stack
├── types_.py     # NamedTuples + TypeAliases: ChapterMatch, Task, ProcessResult,
│                 #   ProcessVolumeResult, CoverMapping, BatchSpecs
├── exit_codes.py # SUCCESS=0, CLI_ERROR=2, MISSING_CHAPTER=3, DUPLICATE_CHAPTER=4,
│                 #   PROCESSING_ERROR=6
├── py.typed      # PEP 561 marker
├── testing.py    # importable helpers (make_cbz, run_packer) for external test use
└── main.py       # entry point shim
```

Test fixtures: `packer/tests/conftest.py` exposes `run_packer`, `make_cbz`, `make_config` as pytest fixtures.

Key behaviours:
- Every `.cbz` **must** contain `ComicInfo.xml` or the script errors and exits
- Chapter ranges: `1..12`, `1,3,5..8` (non-contiguous)
- Named patterns: `--pattern mangafox|mangafire|animeSama|weebcentral` for different filename conventions
- Extras: `16.1`, `16.2` are associated with chapter 16, processed in numeric order
- Batch mode: `--batch "v01:1..3-v02:4..6"` or `--batch-file path` or auto-discovered `.batch` file
- Per-path config: `packer.json` in `--path` dir, or an explicit `--config PATH` (defaults to `<--path>/packer.json`; explicit-but-missing is a hard error). CLI args always override. Resolved in `_apply_path_config` via `load_config_file(cfg_path, required=bool(args.config))`
- `kind: "manga" | "comic"` is an accepted (validated) `packer.json` key but not a packer argument: packer behaves the same; the GUI reads it to pick the convertor preset
- Exit codes: `0` success, `2` CLI error, `3` missing chapter, `4` duplicate, `6` processing error

### editor

Reads EPUB files and injects/dumps/clears metadata defined in a YAML file.

```
src/editor/
├── cli.py            # subcommands: inject / dump / clear (_add_logging_args shared helper)
├── epub_metadata.py  # EPUBMetadata class + _dc_scalar — low-level EPUB I/O via ebooklib
├── editor_full.py    # operations: inject_metadata, dump_metadata, clear_metadata
│                     #   re-exports EPUBMetadata for existing callers
├── exit_codes.py     # SUCCESS = 0, ERROR = 1
├── py.typed          # PEP 561 marker
└── main.py           # entry point shim
```

Test fixtures: `editor/tests/conftest.py` exposes `make_epub`, `make_yaml` as pytest fixtures.

Supported metadata: Dublin Core (`title`, `creator`, `identifier`, `publisher`, `date`, `language`, `subject` from `genre`) + Calibre custom (`series`, `series_index`).

Optional top-level `kind: manga|comic` adds a `Manga` / `Comic` tag to `dc:subject` (skipped if `genre` already has it; any other value fails `inject` before touching files); `dump` emits `kind` back from the tags. The editor never touches the reading direction (KCC writes it in the spine).

YAML format (see `metadatas/*.yaml` for real-world examples):
```yaml
series: "Mashle"
author: "Hajime Komoto"
publisher: "Shueisha"
language: "en-US"          # BCP 47; default "en-US" if omitted
volumes:
  - number: 1
    title: "Magic and Muscles"
    english:
      isbn: "9782380715286"
      release_date: "2021-09-16"
```

**Important:** ISBN and release date live under the `english:` sub-key per volume, NOT at the top level. The `_inject_single` function reads `vol_data.get("english", {})`.

**Chapter titles (`inject`):** optionally relabels the EPUB table-of-contents entries with chapter titles. KCC writes each `Chapter NNN` folder name verbatim as the TOC label; `EPUBMetadata.set_chapter_titles` parses the chapter number back out of that label and rewrites it to `Chapter NNN - <title>`. Matching is by chapter number, so it is volume-agnostic; the `Chapter 000` cover and numbered extras are left untouched. TOC relabelling happens in the same single EPUB save as metadata injection and is independent of the `has_metadata()`/`--force` skip. The titles source is resolved by `_resolve_chapter_titles` in precedence order: (1) `--chapters <file>` CLI flag, (2) `chapters_file:` key in the metadata YAML (path resolved relative to the metadata file), (3) an inline `chapters:` list in the metadata YAML. `_chapters_map` builds the `{number: title}` map from a chapters list; `load_chapters_yaml` wraps it for a standalone `metadatas/chapters_*.yaml` file. No native YAML file-include exists under `safe_load`, hence the `chapters_file:` / inline options.

### convertor

Wraps KindleComicConverter (KCC) to convert volume directories to `.kepub.epub`.

```
src/convertor/
├── cli.py          # CLI orchestration (_build_parser, _build_settings, _process_volumes)
├── kcc_adapter.py  # KCCSettings dataclass, KCCInvocation NamedTuple, convert_volume()
├── __init__.py     # public API: convert_volume()
├── exit_codes.py   # SUCCESS = 0, CLI_ERROR = 2
├── py.typed        # PEP 561 marker
└── main.py         # entry point shim
```

Test fixtures: `convertor/tests/conftest.py` exposes `make_vol`, `run_convertor` as pytest fixtures.

Execution strategy: tries KCC as a Python module first (`kindlecomicconverter`), falls back to CLI (`kcc-c2e`, `kcc`). Defaults target Kobo Libra Colour profile with manga-optimised settings.

Presets: `--preset {manga,comic}` (default `manga`) picks the base `KCCSettings` from `PRESETS` in `kcc_adapter.py` (exported by `convertor`): `comic` = `manga_style=False` (left-to-right), colour kept. Explicit flags (`--[no-]manga-style`, `--profile`, …) always override the preset; resolved in `cli._build_settings`.

### gui (`manga-gui`)

NiceGUI front-end to configure a series ("project") and run packer → convertor → editor. Runs **on the host only** (it must see the real library paths; the Docker image is CLI-only). `uv run manga-gui` → http://127.0.0.1:8080 (`--host`, `--port`, `--data-dir`).

```
gui/src/manga_gui/
├── main.py         # argparse (--host/--port/--data-dir/--loglevel) + _CLIError → ui.run()
├── exit_codes.py   # SUCCESS = 0, CLI_ERROR = 2
├── models.py       # Project, PackerOptions, KCCOptions, EditorOptions, Kind, slugify
├── commands.py     # PURE: Project → list[StepCommand(step, argv, cwd)], .shell()
├── runner.py       # asyncio subprocess runner: line streaming, parse_progress, cancel
├── store.py        # Store: project profiles + run history (XDG or --data-dir)
├── validation.py   # pre-flight Issues, reusing packer / editor loaders
├── scan.py         # .cbz → chapter matches preview, volume dirs, EPUB listing
├── forms.py        # UI-free wizard helpers: batch rows, packer.json / YAML edits, KCC values
├── library.py      # UI-free: folder detection / prefill, create / duplicate project, run summaries
├── volumes.py      # UI-free: volume previews + cached EPUB metadata reads
├── pages/          # projects.py (`/`), history.py (`/project/{slug}/history`), project.py (`/project/{slug}` 6-step ui.stepper)
├── components/     # previews (VolumePreviews), batch_table, covers_grid, json_yaml_editor (FileEditor), kcc_form, log_panel
└── py.typed
```

Key design choices:
- **Steps run as subprocesses** (`sys.executable -m packer.main …`), never by calling `main()` in-process: every `main()` calls `setup_logging()` (clears root handlers), in-process calls cannot be cancelled, and packer uses threads. Logs stream from stderr; progress is parsed from existing log lines; cancel = SIGTERM then SIGKILL; a run stops at the first non-zero exit.
- **Config files are the source of truth**: a project only points to `packer.json`, the batch CSV, the metadata / chapters YAML and stores GUI-only data (paths, KCC overrides, locale, enabled steps). File edits are validated by the CLI loaders (`load_config_file`, `load_yaml_metadata`, …) and written atomically.
- **XDG store**: projects in `$XDG_CONFIG_HOME/manga_manager/projects/<slug>.json`, runs in `$XDG_STATE_HOME/manga_manager/runs/<slug>/<run_id>.{json,log}`; `--data-dir` puts both under one dir (tests).
- **UI-free logic lives outside `pages/` / `components/`** (`forms.py`, `commands.py`, …) so it is unit-tested without NiceGUI.
- **UI tests** use NiceGUI's `user_simulation()` driven by the anyio pytest plugin: mark tests `@pytest.mark.anyio` and take the `gui_user` fixture (`gui/tests/conftest.py`, pages registered on a `gui_store` under `tmp_path`). `nicegui.testing.user_plugin` is NOT registered (a `pytest_plugins` in a non-root conftest is an error).
- **NiceGUI drops page modules from `sys.modules` on teardown**: `gui_user` saves and restores the `manga_gui*` entries, otherwise later imports create new module/class objects and `isinstance` checks break.
- `gui/tests/` has no `__init__.py` (same rule as convertor).

Test fixtures: `gui/tests/conftest.py` exposes `make_project`, `make_library`, `write_json`, `write_yaml`, `py_cmd`, `gui_store`, `gui_user`, `make_epub`, `make_volume_dir`.

---

## Dev Commands

```bash
# Initial setup (--all-packages is required: installs every workspace member + nicegui)
uv sync --all-packages

# Run all tests
uv run pytest .
make test              # via root Makefile (delegates to uv run pytest .)

# Run tests for a single package or file
uv run pytest packer -q
uv run pytest packer/tests/test_core_regex.py -k "test_fma"

# Run with coverage
uv run pytest --cov=packer --cov=convertor --cov=editor --cov=manga_gui --cov-report=html . -q
make test-coverage     # via root Makefile

# Lint (check only)
uv run ruff check .
uv run black --check --diff .
uv run isort --profile black --check-only .
make lint              # runs all three via root Makefile

# Auto-fix lint/format
uv run ruff check --fix .
uv run black .
uv run isort --profile black .
make lint-fix          # via root Makefile

# Type check (mypy — packer and manga_gui; editor/convertor not yet fully annotated)
cd packer && uv run mypy --package packer
cd gui && uv run mypy --package manga_gui
make type-check        # via root Makefile (runs both)

# Run the CLIs
uv run packer --path ./Serie --serie "Berserk" --volume 1 --chapter-range "1..12"
uv run editor inject ./volumes metadata.yaml
uv run editor dump  ./volumes --output out.yaml
uv run editor clear ./volumes
uv run convertor ./volumes [--preset manga|comic] [--force-regen] [--dry-run]
uv run manga-gui [--port 8080] [--data-dir DIR]   # web UI on the host
make gui                                          # same as `uv run manga-gui`
```

> **Note:** CI runs all linters with `|| true` — they report issues but never fail the pipeline. Fix lint errors locally before pushing.

---

## Code Conventions

- **NamedTuples** for structured return types: `ChapterMatch`, `Task`, `ProcessResult`, `ProcessVolumeResult`, `CoverMapping`, `KCCInvocation`, `StepCommand`
- **TypeAlias** for complex composite types: `BatchSpecs = list[tuple[int, list[int]]]` in `types_.py`
- **Config dataclass** in `packer/config.py` — pass `Config` instead of loose kwargs through the call stack
- **`pathlib.Path`** for all filesystem operations (not `os.path`)
- **Named regex patterns** centralised in `core.py` (`NAMED_PATTERNS` dict) — `mangafox`, `mangafire`, `animeSama`, `weebcentral`
- **Logging** with `ColorFormatter` and emoji prefixes; always use `getLogger(__name__)`, never `print()`
- **`--loglevel`** (`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`) + `--verbose` as `DEBUG` shorthand
- **`--dry-run`** must be supported in all write operations — log intent, touch nothing
- **argparse** for all CLIs — no click/typer
- **Doctests** in `core.py` are validated by `tests/test_core_doctest.py`
- **Integration tests** are marked `@pytest.mark.integration` (slow / require external tools)
- Line length: **88** (Black default)

---

## Design Patterns

These patterns are established and must be followed when modifying or extending the codebase.

### CLI Orchestration — `_CLIError` early-exit pattern

All CLI `main()` functions use a private `_CLIError` exception for clean early-exit after logging. Helper functions (`_validate_args`, `_compile_patterns`, etc.) raise `_CLIError` after logging the problem; `main()` catches it and returns the appropriate exit code. This avoids returning `int | tuple` from helpers and keeps `main()` as a flat 20–30 line orchestrator.

```python
class _CLIError(Exception):
    """Raised after logging a CLI-level error so main() can return CLI_ERROR."""

def _validate_args(args) -> None:
    if bad_condition:
        logger.error("...")
        raise _CLIError

def main(argv=None) -> int:
    try:
        covers = _apply_path_config(args)
        _validate_args(args)
        ...
    except _CLIError:
        return CLI_ERROR
    return _run_batch(batch_specs, cfg)
```

### Exit codes

Each package has an `exit_codes.py` with named constants. **Never use bare integer literals** (`return 0`, `return 1`) in CLI code:

| Package | Constants |
|---|---|
| `packer` | `SUCCESS=0`, `CLI_ERROR=2`, `MISSING_CHAPTER=3`, `DUPLICATE_CHAPTER=4`, `PROCESSING_ERROR=6` |
| `editor` | `SUCCESS=0`, `ERROR=1` |
| `convertor` | `SUCCESS=0`, `CLI_ERROR=2` |
| `gui` | `SUCCESS=0`, `CLI_ERROR=2` |

### Module split rationale (editor)

`editor_full.py` was split at a natural boundary:
- `epub_metadata.py` — pure EPUB I/O (`EPUBMetadata` class, `_dc_scalar`). Depends only on `ebooklib`. No business logic.
- `editor_full.py` — operations (`inject_metadata`, `dump_metadata`, `clear_metadata`). Imports `EPUBMetadata` from `epub_metadata`. Also re-exports `EPUBMetadata` so existing callers (`from editor.editor_full import EPUBMetadata`) continue to work without changes.

### Worker decomposition (packer)

`process_volume` in `worker.py` is decomposed into:
- `_plan_tasks(mapping, chapter_range)` — pure: builds ordered `Task` list from chapter mapping
- `_copy_cover(volume_dir, volume, cfg)` — side-effect: copies cover.webp if configured
- `_run_tasks(tasks, cfg)` — returns `list[str]` of moved files on success, `None` on first error

`process_volume` itself is ~40 lines: build mapping → validate → plan → mkdir → cover → run → cleanup.

### Test fixture conventions

Each package's `conftest.py` exposes fixtures as factory-pattern fixtures (fixture returns a callable):

```python
# packer/tests/conftest.py
@pytest.fixture
def make_cbz():
    def _make(path, name, include_comicinfo=True): ...
    return _make

@pytest.fixture
def make_config():
    def _make(src, dest=None, *, serie="Manga", volume=1, ...): ...
    return _make
```

**convertor tests are NOT a package** (no `__init__.py`). Do not add one — it would cause pytest plugin registration conflicts across the monorepo (`tests.conftest` collision). Use fixtures as function parameters instead of importing from conftest.

### Coverage instrumentation — direct `main()` calls

Tests that need coverage must call `main()` directly, never via subprocess. Subprocess calls do not appear in coverage reports.

```python
# CORRECT — instruments coverage
from packer.cli import main
rc = main(["--path", str(src), "--serie", "Manga", ...])

# WRONG — subprocess never counted by coverage
run_packer(tmp_path, ["--path", str(src), ...])  # use only for integration/smoke tests
```

The `run_packer` / `run_convertor` fixtures in conftest launch subprocesses and are reserved for smoke tests that verify the full CLI pipeline end-to-end.

### `caplog` vs `capsys` for packer log assertions

`packer.cli.setup_logging()` calls `root.handlers.clear()`, which removes pytest's `caplog` handler. This means **`caplog` does not capture packer log records** when `main()` is called directly. Use `capsys.readouterr().err` instead:

```python
# WRONG — caplog captures nothing after setup_logging()
def test_foo(tmp_path, caplog):
    main([...])
    assert "not found" in caplog.text  # always fails

# CORRECT
def test_foo(tmp_path, capsys):
    main([...])
    assert "not found" in capsys.readouterr().err
```

`caplog` works fine in worker/core tests where `setup_logging()` is not called.

---

## Roadmap / TODOs

See `ROADMAP.md` for the full task list. Key open items:

- **packer:** `ComicInfo.xml` robustness, `--flatten`/`--keep-structure`, rework concurrency, `--skip-missing`/`--continue-on-error`
- **editor:** Calibre tag/ID injection, Kobo library collection support
- **convertor:** parallelize workers, parametrise KCC settings
- **gui:** projects page (duplicate / delete, last-run status) + run history page (G6), volume previews (G7)
- **comics:** comic filename patterns (K3, blocked on sample files), optional `Issue` TOC label (K5)
- **CI:** multi-Python matrix (3.10–3.12), reviewdog PR annotations, optional KCC integration job
