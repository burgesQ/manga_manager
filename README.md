# manga_manager

[![CI](https://github.com/burgesQ/manga_manager/actions/workflows/ci.yml/badge.svg)](https://github.com/burgesQ/manga_manager/actions/workflows/ci.yml)
[![Docker](https://github.com/burgesQ/manga_manager/actions/workflows/docker.yml/badge.svg)](https://github.com/burgesQ/manga_manager/actions/workflows/docker.yml)
[![CodeQL](https://github.com/burgesQ/manga_manager/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/burgesQ/manga_manager/security/code-scanning)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?labelColor=ef8336)](https://pycqa.github.io/isort/)
[![mypy: checked](https://img.shields.io/badge/mypy-checked-2a6db2)](https://mypy-lang.org/)
[![Open in GitHub Codespaces](https://img.shields.io/badge/Codespaces-open-181717?logo=github)](https://codespaces.new/burgesQ/manga_manager)

A suite of CLI tools — plus an optional local web UI — to build a manga (or comic) library for Kobo e-readers, from raw chapter archives to polished `.kepub.epub` files with full metadata.

**Platform:** Linux (tested on Linux Mint 22.3 / Debian 13) · **Python:** 3.12+ · **Package manager:** [uv](https://docs.astral.sh/uv/)

---

## Overview

`manga_manager` covers the full pipeline from downloaded chapter archives to a Kobo-ready library:

```
.cbz archives (Tachiyomi, etc.)
        │
        ▼
   ┌─────────┐
   │  packer │  ──▶  groups chapters into volume dirs, extracts images
   └─────────┘
        │
        ▼
Volume dir  [Berserk v01/]
        │
        ▼
   ┌───────────┐
   │ convertor │  ──▶  converts to .kepub.epub via KindleComicConverter
   └───────────┘
        │
        ▼
Berserk v01.kepub.epub
        │
        ▼
   ┌────────┐
   │ editor │  ──▶  injects metadata (title, author, ISBN, series…) from YAML
   └────────┘
        │
        ▼
Berserk v01.kepub.epub (with metadata)  →  Kobo
```

| Tool | Version | What it does |
|---|---|---|
| **packer** | v0.1.0 | Groups `.cbz` chapter archives into volume directories with extracted chapter subdirs |
| **convertor** | v1.0 | Converts volume directories to `.kepub.epub` via KCC (`--preset manga\|comic`) |
| **editor** | v1.0 | Injects / dumps / clears EPUB metadata from YAML files |
| **manga-gui** (`gui/`) | v0.1.0 | Local web UI to configure a series and run packer → convertor → editor (see [GUI](#gui)) |

---

## Prerequisites

- **Python 3.12+** — check with `python3 --version`
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** — fast Python package manager

`kindlecomicconverter` (KCC) is a declared Python dependency and is installed automatically by `uv sync --all-packages` — no separate installation needed.

---

## Installation

```console
# Clone the repository
git clone https://github.com/burgesQ/manga_manager.git
cd manga_manager

# Install every workspace package (packer, editor, convertor, manga-gui) and dev tools
uv sync --all-packages
```

> **Use `--all-packages`.** The root project is only the workspace container: a plain
> `uv sync` does not install the workspace members, so the `packer` / `editor` /
> `convertor` / `manga-gui` commands and the GUI's `nicegui` dependency would be
> missing (or removed from an existing `.venv`).

The CLIs (and the GUI) are now available via `uv run`:

```console
uv run packer --help
uv run editor --help
uv run convertor --help
uv run manga-gui --help
```

### Docker

A prebuilt image with the **three CLIs only** (packer, editor, convertor, plus KCC) is
published to GHCR on every push to `main`. `manga-gui` and NiceGUI are deliberately not
in the image: the GUI runs on the host (see [GUI](#gui)). Mount your library and run as
your own user so the generated files are not owned by root:

```bash
docker run --rm -it --user "$(id -u):$(id -g)" \
  -v "$PWD/Manga:/data" -w /data \
  ghcr.io/burgesq/manga_manager convertor ./volumes --dry-run
```

The same image backs the dev container: open the repo in **GitHub Codespaces** (badge
above) or with VS Code *Dev Containers* to edit, lint and test without a local setup.

---

## Shell completion

Each CLI can emit a completion script via `--print-completion {bash,zsh,tcsh}` (powered by
[`shtab`](https://github.com/iterative/shtab)).

> **Important — completion binds to the command _word_.** The generated script registers
> completion for `packer` / `editor` / `convertor`. It therefore fires on `packer <TAB>` but
> **not** on `uv run packer <TAB>` — in that form the shell is completing `uv`'s arguments, not
> the CLI's. Pick one of the two setups below.

### Option A — use the installed entry points directly (recommended)

`uv sync --all-packages` installs the console scripts into `.venv/bin/`. Activate the venv (or put that dir on
`PATH`) so `packer` is a real command, then install the completion:

```console
source .venv/bin/activate            # now `packer`, `editor`, `convertor` are on PATH

# zsh — drop the script on your fpath, then recompile completions
packer    --print-completion zsh > ~/.zfunc/_packer
editor    --print-completion zsh > ~/.zfunc/_editor
convertor --print-completion zsh > ~/.zfunc/_convertor
# ensure ~/.zfunc is on $fpath before `compinit` in ~/.zshrc:
#   fpath=(~/.zfunc $fpath); autoload -Uz compinit && compinit

# bash
packer --print-completion bash | sudo tee /etc/bash_completion.d/packer >/dev/null
```

Now `packer <TAB>` completes. (No `uv run` prefix — the venv is active.)

### Option B — keep the `uv run` workflow via wrapper functions

If you prefer not to activate the venv, define wrapper functions named after the CLIs; the
`#compdef packer` completion attaches to the function just as it would to a binary:

```zsh
# ~/.zshrc
MM=~/repo/manga_manager
packer()    { uv run --project $MM packer    "$@"; }
editor()    { uv run --project $MM editor    "$@"; }
convertor() { uv run --project $MM convertor "$@"; }
```

Install the completion scripts as in Option A. Now `packer <TAB>` completes **and** runs via
`uv run` under the hood. (Typing the literal `uv run packer <TAB>` still won't complete — use the
`packer` function instead.)

---

## Full Workflow Example

Starting from a folder of `.cbz` chapter files downloaded from Tachiyomi:

```
~/Downloads/Berserk/
├── Berserk - Chapter 001.cbz
├── Berserk - Chapter 002.cbz
├── ...
└── Berserk - Chapter 012.cbz
```

### Step 1 — Pack chapters into a volume

```console
uv run packer \
  --path ~/Downloads/Berserk \
  --serie "Berserk" \
  --volume 1 \
  --chapter-range "1..12"
```

Result:

```
~/Downloads/Berserk/
└── Berserk v01/
    ├── Berserk - Chapter 001.cbz
    ├── Chapter 001/
    │   ├── 001.jpg
    │   ├── 002.jpg
    │   └── ComicInfo.xml
    ├── Berserk - Chapter 002.cbz
    ├── Chapter 002/
    ...
```

### Step 2 — Convert to Kobo format

```console
uv run convertor ~/Downloads/Berserk
```

Output: `~/Downloads/Berserk/Berserk v01.kepub.epub` — ready to copy to your Kobo.

### Step 3 — Create a metadata file

```yaml
# berserk.yaml
series: "Berserk"
author: "Kentaro Miura"
publisher: "Dark Horse Comics"
language: "en"

volumes:
  - number: 1
    title: "Black Swordsman"
    english:
      isbn: "978-1-56931-900-0"
      release_date: "2003-08-19"
```

### Step 4 — Inject metadata into the EPUB

```console
uv run editor inject ~/Downloads/Berserk berserk.yaml
```


---

## GUI

`manga-gui` (workspace member `gui/`, built with [NiceGUI](https://nicegui.io)) is a
local web UI to set up and run the whole pipeline per series ("project") instead of
hand-editing config files and chaining three commands with matching paths.

**It runs on the host, not in Docker**: it must see your real library paths, and the
Docker image ships the CLIs only.

```console
uv sync --all-packages          # once: installs manga-gui and nicegui
uv run manga-gui                # → http://127.0.0.1:8080
make gui                        # same thing
```

| Option | Default | Purpose |
|---|---|---|
| `--host` | `127.0.0.1` | Interface to bind (local only by default) |
| `--port` | `8080` | Port to listen on |
| `--data-dir PATH` | XDG dirs | Store projects, runs and settings under `PATH/projects`, `PATH/runs`, `PATH/settings.json` |
| `--library-root PATH` | saved setting | Library root holding the series folders (this session only) |
| `--metadata-dir PATH` | saved setting | Folder of `packer_<key>.json` / `<key>.yaml` / `chapters_<key>.yaml` / `vols_<key>.csv` (this session only) |
| `--loglevel` / `--verbose` | `INFO` | Log level |
| `--version` | | Print the version |

**Import existing series** (`manga-gui import`): matches the per-series files of a
metadata dir to the series folders of a library root (`<root>/<LANG>/<serie>/`) and
creates one project profile per series. Your files are never modified; only profiles
are written, and existing ones are skipped unless `--overwrite`.

```console
uv run manga-gui import --library-root ~/Shelf --metadata-dir ./metadatas --dry-run
uv run manga-gui import --library-root ~/Shelf --metadata-dir ./metadatas --save-settings
```

**What it does:**

- **Projects** (`/`): project cards with last-run status, open / duplicate / delete, a
  *New project* form that prefills serie, pattern and kind from an existing `packer.json`
  (or from a series folder picked in the library), and a *Library* card (library root,
  metadata dir, *Import…* dialog doing the same as `manga-gui import`).
- **History** (`/project/<slug>/history`): past runs with per-step exit codes, command
  lines and full logs.
- **Project wizard** (`/project/<slug>`), six steps:
  1. **Library**: name, kind (Manga / Comic), source and destination folders, and a
     scan of the `.cbz` files showing detected chapters, unmatched files and duplicates.
  2. **Packer**: serie, pattern / regexes, workers, volumes (single volume, batch spec
     or batch CSV file, edited as a table), covers per volume, and a raw `packer.json`
     editor validated by packer's own loader.
  3. **Convertor**: KCC settings on top of the `manga` / `comic` preset.
  4. **Metadata**: metadata YAML (series fields, volumes table, chapter titles preview,
     raw YAML editor), chapters YAML, locale, `--force`.
  5. **Review & Run**: pre-flight checks, a checkbox per step, resolved paths, the
     equivalent shell commands, then *Dry-run* / *Run* / *Cancel* with live logs.
  6. **Volumes**: packed volume folders with cover and chapter count, generated
     `.kepub.epub` files and their injected metadata (refreshed after every run).

**Design:** the real config files (`packer.json`, batch CSV, metadata / chapters YAML)
stay the source of truth: a project only points to them, so the CLIs keep working
without the GUI. Each step runs as a subprocess (`python -m packer.main …`), so its logs
stream live and it can be cancelled; the run stops at the first failing step.

**Where data is stored** (override both with `--data-dir`):

| What | Location |
|---|---|
| Project profiles | `$XDG_CONFIG_HOME/manga_manager/projects/<slug>.json` (default `~/.config/manga_manager/projects/`) |
| Run history (per-step argv, exit code, duration + full log) | `$XDG_STATE_HOME/manga_manager/runs/<slug>/<run_id>.{json,log}` (default `~/.local/state/manga_manager/runs/`) |
| Settings (library root, metadata dir) | `$XDG_CONFIG_HOME/manga_manager/settings.json` |

See [`gui/README.md`](gui/README.md) for details.

---

## Comics

Comics differ from manga in two ways: they are in **colour** and read
**left-to-right**. The defaults assume manga (right-to-left), so tell each tool:

| Where | Setting | Effect |
|---|---|---|
| `convertor` | `--preset comic` | `manga_style` off (left-to-right), colour kept; explicit flags still override the preset |
| `packer.json` | `"kind": "comic"` | Read by `manga-gui` to pick the convertor preset; packer itself behaves the same |
| metadata YAML | `kind: comic` | `editor inject` adds a `Comic` tag (`dc:subject`); `editor dump` emits it back |
| `manga-gui` | *Kind* toggle (Library step) | Sets the convertor preset and writes `kind` to `packer.json` |

```console
uv run convertor ./Saga --preset comic
```

> **Not supported yet:** comic filename patterns (issue numbers such as
> `Saga 001 (2012) (Digital).cbz`) — see **K3** in [ROADMAP.md](ROADMAP.md). Use
> `--chapter-regex` / `--extra-regex` meanwhile; note that every `.cbz` still needs a
> `ComicInfo.xml`.

---

## packer

Groups `.cbz` chapter archives into a volume directory and extracts each into a `Chapter NNN/` subdirectory.

### Requirements

Every `.cbz` must contain a `ComicInfo.xml` — packer validates this before processing. Archives from Tachiyomi include it by default.

### Basic usage

```console
uv run packer \
  --path <dir>           \  # folder containing .cbz files
  --serie <name>         \  # series name (used to name the volume dir)
  --volume <N>           \  # volume number
  --chapter-range <range>   # e.g. "1..12" or "1,3,5..8"
```

### Chapter ranges

```console
--chapter-range "1..12"       # chapters 1 to 12 (inclusive)
--chapter-range "1,3,5..8"    # chapters 1, 3, 5, 6, 7, 8
--chapter-range "16"          # single chapter (with extras: 16.1, 16.2…)
```

### Named filename patterns

Packer ships with pre-configured regex patterns for common download sources.
Pass `--pattern <name>` to select one:

| Flag | Matches | Extras | Source |
|---|---|---|---|
| `default` | `Chapter 001`, `Ch.001`, `Ch 1` | `Chapter 001.5` | "read dot net" sites (e.g. `readberserk.net`, generic) |
| `mangafox` | `Ch.013`, `Ch 013`, `Chapter 013` | `Ch.013.5` | MangaFox, Tachiyomi downloads |
| `mangafire` | `Chap 013`, `Chap.013` | `Chap 013.5` | MangaFire |
| `animeSama` | `Chapitre 013`, `Chap 013` | `Chapitre 013.5` | animesama.fr (French scans) |
| `weebcentral` | `Unknown_# 327_<hash>` | `Unknown_# 327.1_<hash>` | WeebCentral |

**Regex details:**

| Flag | Chapter regex | Extra regex |
|---|---|---|
| `default` | `(?i)chapter[\s._-]*0*(\d+)` or `(?i)ch[\s._-]*0*(\d+)` | same with `\.(\d+)` suffix |
| `mangafox` | `(?i)ch(?:\.\|apter)?[\s._-]*0*(\d+)` | `…\.(\d+)` |
| `mangafire` | `(?i)chap(?:\.\|ter)?[\s._-]*0*(\d+)` | `…\.(\d+)` |
| `animeSama` | `(?i)chap(?:\.\|itre)?[\s._-]*0*(\d+)` | `…\.(\d+)` |
| `weebcentral` | `#\s*0*(\d+)` | `…\.(\d+)` |

```console
# MangaFox download: "Ch.001 Title.cbz", "Ch.001.5.cbz"
uv run packer --path ./Mashle --serie "Mashle" --volume 1 \
  --chapter-range "1..8" --pattern mangafox

# MangaFire download: "Chap 016.cbz", "Chap 016.1.cbz"
uv run packer --path ./FMA --serie "FMA" --volume 4 \
  --chapter-range "16" --pattern mangafire

# Override with a fully custom regex
uv run packer --path ./Series --serie "Series" --volume 1 \
  --chapter-range "1..10" \
  --chapter-regex "Episode ([0-9]+)" \
  --extra-regex "Episode ([0-9]+)\.([0-9]+)"
```

### Extras (e.g. chapter 16.1, 16.2)

Extra chapters are automatically associated with their parent chapter number and processed in numeric order:

```console
# Processes Chapter 16, then 16.1, then 16.2 in order
uv run packer --path ./FMA --serie "FMA" --volume 4 \
  --chapter-range "16" --pattern mangafire
```

### Batch mode — multiple volumes at once

```console
# Inline batch spec
uv run packer --path ./Berserk --serie "Berserk" \
  --batch "v01:1..12-v02:13..24-v03:25..36"

# From a batch file (one entry per line: v01,1..12)
uv run packer --path ./Berserk --serie "Berserk" --batch-file berserk.batch

# Auto-discovery: packer looks for a .batch file in --path automatically
```

### Per-path config file (`packer.json`)

Place a `packer.json` in the source directory to set defaults. CLI arguments always override it.
By default packer looks for `<--path>/packer.json`; pass `--config PATH` to load the config from an
explicit location instead (a missing `--config` file is a hard error, unlike the optional default).

```json
{
  "serie": "Berserk",
  "pattern": "mangafox",
  "nb_worker": 2,
  "kind": "manga"
}
```

`kind` (`manga` | `comic`, optional) does not change packer's behaviour; `manga-gui`
uses it to pick the convertor preset (see [Comics](#comics)).

### Cover image

Place a `cover.webp` in the volume directory before running `convertor`. It will be injected as the first page in the EPUB.

### All options

```
--path PATH              source directory containing .cbz files
--serie NAME             series name
--volume N               volume number
--chapter-range RANGE    chapter range: "1..12", "1,3,5..8"
--dest PATH              output root (default: same as --path)
--pattern NAME           named pattern: mangafox | mangafire | animeSama | weebcentral
--chapter-regex REGEX    custom regex for main chapters
--extra-regex REGEX      custom regex for extra chapters
--batch SPEC             inline batch: "v01:1..3-v02:4..6"
--batch-file PATH        batch file path
--nb-worker N            parallel workers (default: 1)
--force                  overwrite existing chapter directories
--dry-run                simulate without touching the filesystem
--verbose / --loglevel   control log output
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `2` | CLI / argument error |
| `3` | Missing chapter |
| `4` | Duplicate chapter match |
| `6` | Processing error |

---

## editor

Manages EPUB metadata from YAML files. Supports a single `.epub` file or a directory of EPUBs.

### Subcommands

#### `inject` — write metadata into EPUBs

```console
uv run editor inject <path> <metadata.yaml> [options]

# Examples
uv run editor inject ./Berserk berserk.yaml
uv run editor inject "./Berserk v01.epub" berserk.yaml --force
uv run editor inject ./Berserk berserk.yaml --dry-run --verbose
```

| Option | Description |
|---|---|
| `--force` | Overwrite metadata if it already exists |
| `--dry-run` | Simulate without writing |

#### `dump` — extract metadata from EPUBs to YAML

```console
uv run editor dump <path> [--output file.yaml]

# Print to stdout
uv run editor dump ./Berserk

# Save to file
uv run editor dump ./Berserk --output current.yaml
```

#### `clear` — remove all custom metadata

```console
uv run editor clear <path> [--dry-run]
```

### Metadata YAML format

```yaml
series: "Berserk"
author: "Kentaro Miura"
publisher: "Dark Horse Comics"
language: "en"                    # BCP 47 code; default: "en-US" if omitted
kind: "manga"                     # optional: manga | comic → Manga / Comic tag

volumes:
  - number: 1
    title: "Black Swordsman"
    english:                      # locale block, picked with --locale (default english)
      isbn: "978-1-56931-900-0"
      release_date: "2003-08-19"
  - number: 2
    title: "The Shadow"
    language: "fr"                # per-volume override
    english:
      isbn: "978-1-56931-980-2"
      release_date: "2004-01-01"
```

**Top-level keys:**

| Key | Required | Description |
|---|---|---|
| `series` | yes | Series name → `calibre:series` |
| `author` | yes | Author name → `dc:creator` |
| `publisher` | no | Publisher → `dc:publisher` |
| `language` | no | Default language (BCP 47); falls back to `en-US` |
| `kind` | no | `manga` or `comic`: adds a `Manga` / `Comic` tag (`dc:subject`) |

**Per-volume keys:**

| Key | Description |
|---|---|
| `number` | Volume number → `calibre:series_index` |
| `title` | Volume title → `dc:title` |
| `<locale>.isbn` | ISBN → `dc:identifier` (under `english:` / `japanese:` / `french:`, see `--locale`) |
| `<locale>.release_date` | Release date (YYYY-MM-DD) → `dc:date` |
| `language` | Overrides series-level language for this volume |

### Supported metadata fields

- **Dublin Core:** `title`, `creator`, `identifier` (ISBN), `publisher`, `date`, `language`
- **Calibre custom:** `series`, `series_index`

See `metadatas/` for real-world examples (Mashle, FMA, Boruto, etc.).

---

## convertor

Converts volume directories into `.kepub.epub` files using [KindleComicConverter (KCC)](https://github.com/ciromattia/kcc).

### Basic usage

```console
# Convert all volume directories under a root folder
uv run convertor ./Berserk

# Regenerate even if output already exists
uv run convertor ./Berserk --force-regen

# Dry run
uv run convertor ./Berserk --dry-run --verbose
```

For each subdirectory under `<root>`, convertor creates a `<VolumeDir>.kepub.epub` sibling file.

```
Berserk/
├── Berserk v01/          ← input dir
│   ├── Chapter 001/
│   └── ...
├── Berserk v01.kepub.epub  ← generated output
```

### KCC settings

`--preset manga` (default) targets the recommended Kobo manga profile (right-to-left);
`--preset comic` is the same but left-to-right (see [Comics](#comics)). Any explicit flag
overrides the preset. Override only what you need:

```console
uv run convertor ./Berserk \
  --profile KoF              # different Kobo model (KoF = Kobo Forma)
  --no-manga-style           # disable right-to-left reading order
  --no-hq                    # disable high-quality mode
  --no-forcecolor            # grayscale output
  --rotation 0               # no page rotation (default: 2 = 90° CCW)
  --cropping 1               # safe cropping (default: 2 = aggressive)
```

| Flag | Default | Description |
|---|---|---|
| `--preset {manga,comic}` | `manga` | Base settings: `comic` turns `--manga-style` off |
| `--profile` | `KoLC` | KCC device profile (`KoLC` = Kobo Libra Colour) |
| `--[no-]manga-style` | on (`manga`) / off (`comic`) | Right-to-left reading direction |
| `--[no-]hq` | on | High-quality mode |
| `--[no-]forcecolor` | on | Force colour output |
| `--rotation 0-3` | `2` | Page rotation: 0=none, 1=90CW, 2=90CCW, 3=180° |
| `--cropping 0-2` | `2` | Cropping: 0=off, 1=safe, 2=aggressive |

### Cover image

If a `cover.webp` file exists at the root of a volume directory, convertor automatically places it as the first page (`Chapter 000/`) before invoking KCC, then cleans it up afterwards.

```
Berserk v01/
├── cover.webp              ← optional: will become the EPUB cover
├── Berserk - Ch.001.cbz
├── Chapter 001/
└── ...
```

---

## Development

```console
# Install all workspace packages (including manga-gui) and dev tools
uv sync --all-packages

# Run the full test suite
uv run pytest .

# Run tests for a single package
uv run pytest packer -q
uv run pytest editor -q
uv run pytest gui -q
cd convertor && uv run pytest

# Run with coverage
uv run pytest --cov=packer --cov=convertor --cov=editor --cov=manga_gui --cov-report=html . -q

# Linting & formatting
uv run ruff check .
uv run black --check --diff .
uv run isort --profile black --check-only .

# Type checking (packer + manga_gui)
make type-check

# Apply auto-fixes
uv run ruff check --fix .
uv run black .
uv run isort --profile black .

# Coverage HTML report (packer)
make -C packer coverage-html
```

### Project structure

```
manga_manager/
├── packer/           # .cbz → volume dirs
│   ├── src/packer/
│   └── tests/
├── editor/           # EPUB metadata management
│   ├── src/editor/
│   └── tests/
├── convertor/        # volume dirs → .kepub.epub
│   ├── src/convertor/
│   └── tests/
├── gui/              # manga-gui: NiceGUI web UI (host only)
│   ├── src/manga_gui/
│   └── tests/
├── metadatas/        # example YAML metadata files
├── CLAUDE.md         # guidance for Claude Code sessions
├── ROADMAP.md        # backlog and open tasks
└── pyproject.toml    # uv workspace root
```

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full backlog. Current open priorities:

- **packer:** `ComicInfo.xml` robustness, `--flatten`/`--keep-structure`, concurrency rework
- **editor:** Calibre tag/ID injection, Kobo collection support
- **convertor:** parallel workers, KCC settings via `packer.json`
- **GUI:** projects page (duplicate / delete), run history page, volume previews
- **Comics:** comic filename patterns (needs sample files), optional `Issue` TOC label
- **CI:** multi-Python matrix, reviewdog annotations
