# manga_manager

A suite of CLI tools to build a manga library for Kobo e-readers — from raw chapter archives to polished `.kepub.epub` files with full metadata.

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
   ┌────────┐
   │ editor │  ──▶  injects metadata (title, author, ISBN, series…) from YAML
   └────────┘
        │
        ▼
   ┌───────────┐
   │ convertor │  ──▶  converts to .kepub.epub via KindleComicConverter
   └───────────┘
        │
        ▼
Berserk v01.kepub.epub  →  Kobo
```

| Tool | Version | What it does |
|---|---|---|
| **packer** | v0.1.0 | Groups `.cbz` chapter archives into volume directories with extracted chapter subdirs |
| **editor** | v1.0 | Injects / dumps / clears EPUB metadata from YAML files |
| **convertor** | v1.0 | Converts volume directories to `.kepub.epub` via KCC |

---

## Prerequisites

- **Python 3.12+** — check with `python3 --version`
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** — fast Python package manager

`kindlecomicconverter` (KCC) is a declared Python dependency and is installed automatically by `uv sync` — no separate installation needed.

---

## Installation

```console
# Clone the repository
git clone https://github.com/burgesQ/manga_manager.git
cd manga_manager

# Install all packages and dev dependencies
uv sync
```

The three CLIs are now available via `uv run`:

```console
uv run packer --help
uv run editor --help
uv run convertor --help
```

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
    isbn: "978-1-56931-900-0"
    date: "2003-08-19"
```

### Step 4 — Inject metadata into the EPUB

```console
uv run editor inject ~/Downloads/Berserk berserk.yaml
```


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

```json
{
  "serie": "Berserk",
  "pattern": "mangafox",
  "nb_worker": 2
}
```

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

volumes:
  - number: 1
    title: "Black Swordsman"
    isbn: "978-1-56931-900-0"
    date: "2003-08-19"
  - number: 2
    title: "The Shadow"
    isbn: "978-1-56931-980-2"
    date: "2004-01-01"
    language: "fr"                # per-volume override
```

**Top-level keys:**

| Key | Required | Description |
|---|---|---|
| `series` | yes | Series name → `calibre:series` |
| `author` | yes | Author name → `dc:creator` |
| `publisher` | no | Publisher → `dc:publisher` |
| `language` | no | Default language (BCP 47); falls back to `en-US` |

**Per-volume keys:**

| Key | Description |
|---|---|
| `number` | Volume number → `calibre:series_index` |
| `title` | Volume title → `dc:title` |
| `isbn` | ISBN → `dc:identifier` |
| `date` | Release date (YYYY-MM-DD) → `dc:date` |
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

All settings default to the recommended Kobo Manga profile. Override only what you need:

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
| `--profile` | `KoLC` | KCC device profile (`KoLC` = Kobo Libra Colour) |
| `--[no-]manga-style` | on | Right-to-left reading direction |
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
# Install all dependencies (including dev tools)
uv sync

# Run the full test suite
uv run pytest .

# Run tests for a single package
uv run pytest packer -q
uv run pytest editor -q
cd convertor && uv run pytest

# Run with coverage
uv run pytest --cov=packer --cov=convertor --cov=editor --cov-report=html . -q

# Linting & formatting
uv run ruff check .
uv run black --check --diff .
uv run isort --profile black --check-only .

# Type checking
uv run mypy packer/src editor/src convertor/src

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
- **CI:** multi-Python matrix, reviewdog annotations
