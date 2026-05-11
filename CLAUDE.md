# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`manga_manager` is a Python 3.12+ monorepo (uv workspace) of three CLI tools to manage manga libraries targeting Kobo e-readers.

**Full workflow:**
```
*.cbz archives → packer → volume dirs → editor (metadata) → convertor → *.kepub.epub (Kobo)
```

**Packages:**
| Package | Version | Purpose |
|---|---|---|
| `packer` | v0.1.0 | Group `.cbz` chapter archives into volume directories with extracted chapter subdirs |
| `editor` | v1.0 | Inject / dump / clear EPUB metadata from YAML files |
| `convertor` | v1.0 | Convert volume directories to `.kepub.epub` via KindleComicConverter (KCC) |

- **Language:** Python 3.12+ — `packer` uses stdlib only, no external deps
- **Package manager:** `uv` workspace (see root `pyproject.toml`)
- **Platform:** Linux (tested on Linux Mint 22.3 / Debian 13)

---

## Architecture

### packer

Reads `.cbz` archives from `--path`, matches chapter numbers via regex patterns, creates a volume directory (`[Serie] vNN`), moves archives in, and extracts each into a `Chapter NNN/` subdirectory.

```
src/packer/
├── cli.py       # argparse CLI, config building, orchestration
├── core.py      # file discovery, regex parsing, pattern matching
├── worker.py    # per-chapter processing (move → mkdir → extract)
├── config.py    # Config dataclass (centralizes all runtime options)
├── types_.py    # NamedTuples: ChapterMatch, Task, ProcessResult, ProcessVolumeResult
└── main.py      # entry point shim
```

Test helpers (`run_packer`, `make_cbz`) live in both `packer/tests/conftest.py` (pytest fixtures) and `packer.testing` (importable module) — use either in new tests.

Key behaviors:
- Every `.cbz` **must** contain `ComicInfo.xml` or the script errors and exits
- Chapter ranges: `1..12`, `1,3,5..8` (non-contiguous)
- Named patterns: `--pattern mashle|fma|animeSama` for different filename conventions
- Extras: `16.1`, `16.2` are associated with chapter 16, processed in numeric order
- Batch mode: `--batch "v01:1..3-v02:4..6"` or `--batch-file path` or auto-discovered `.batch` file
- Per-path config: `packer.json` in `--path` dir (CLI args always override)
- Exit codes: `0` success, `2` CLI error, `3` missing chapter, `4` duplicate, `6` processing error

### editor

Reads EPUB files and injects/dumps/clears metadata defined in a YAML file.

```
src/editor/
├── cli.py          # subcommands: inject / dump / clear
├── editor_full.py  # active core: Dublin Core + Calibre metadata via ebooklib
├── editor.py       # older/simpler implementation — not used by CLI, kept as reference
└── main.py         # entry point shim
```

Supported metadata: Dublin Core (`title`, `creator`, `identifier`, `publisher`, `date`, `language`, `description`) + Calibre custom (`series`, `series_index`, `rating`, `tags`).

YAML format (see `metadatas/*.yaml` for examples):
```yaml
series: "Mashle"
author: "Hajime Komoto"
volumes:
  - number: 1
    title: "Magic and Muscles"
    isbn: "9782380715286"
    date: "2021-09-16"
```

### convertor

Wraps KindleComicConverter (KCC) to convert volume directories to `.kepub.epub`.

```
src/convertor/
├── cli.py          # CLI orchestration
├── kcc_adapter.py  # KCCAdapter class + KCCInvocation NamedTuple
├── __init__.py     # public API: convert_volume()
└── main.py         # entry point shim
```

Execution strategy: tries KCC as a Python module first (`runpy`), falls back to CLI (`kcc`, `kcc-c2e`). Defaults target Kobo Libra Colour profile with manga-optimized settings.

---

## Dev Commands

```bash
# Initial setup
uv sync

# Run all tests
uv run pytest .

# Run tests for a single package or file
uv run pytest packer -q
uv run pytest packer/tests/test_core_regex.py -k "test_fma"

# Run with coverage (as CI does)
uv run pytest --cov=packer --cov=convertor --cov=editor --cov-report=html . -q

# Lint (ruff)
uv run ruff check .

# Format check (black)
uv run black --check --diff .

# Import order check
uv run isort --profile black --check-only .

# Type check (packer only; mypy not yet configured for editor/convertor)
uv run mypy packer/src

# Apply auto-fixes
uv run ruff check --fix .
uv run black .
uv run isort --profile black .

# Coverage HTML (packer Makefile)
make -C packer coverage-html

# Run the CLIs
uv run packer --path ./Serie --serie "Berserk" --volume 1 --chapter-range "1..12"
uv run editor inject ./volumes metadata.yaml
uv run editor dump  ./volumes --output out.yaml
uv run editor clear ./volumes
uv run convertor ./volumes [--force-regen] [--dry-run]
```

> **Note:** CI runs all linters with `|| true` — they report issues but never fail the pipeline. Fix lint errors locally before pushing.

---

## Code Conventions

- **NamedTuples** for structured return types: `ChapterMatch`, `Task`, `ProcessResult`, `ProcessVolumeResult`, `KCCInvocation`
- **Config dataclass** in `packer/config.py` — pass `Config` instead of loose kwargs through the call stack
- **`pathlib.Path`** for all filesystem operations (not `os.path`)
- **Named regex patterns** centralized in `core.py` (`CHAPTER_PATTERNS` dict) — `mashle`, `fma`, `animeSama`
- **Logging** with `ColorFormatter` and emoji prefixes; always use `getLogger(__name__)`, never `print()`
- **`--loglevel`** (`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`) + `--verbose` as `DEBUG` shorthand
- **`--dry-run`** must be supported in all write operations — log intent, touch nothing
- **argparse** for all CLIs — no click/typer
- **Doctests** in `core.py` are validated by `tests/test_core_doctest.py`
- **Integration tests** are marked `@pytest.mark.integration` (slow / require external tools)
- Line length: **88** (Black default)

---

## Roadmap / TODOs

See `ROADMAP.md` for the full task list. Key open items:

- **packer:** `ComicInfo.xml` robustness, `--flatten`/`--keep-structure`, rework concurrency, `--skip-missing`/`--continue-on-error`
- **editor:** Calibre tag/ID injection, Kobo library collection support
- **convertor:** parallelize workers, parametrize KCC settings
- **CI:** multi-Python matrix (3.10–3.12), reviewdog PR annotations, optional KCC integration job
