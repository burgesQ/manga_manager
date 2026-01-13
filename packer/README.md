## packer

The `packer` purpose: for a given series, create a volume directory, move
chapter archives (`.cbz`) into it, and extract each archive into a chapter
subdirectory.

### TLDR

Test

```console
$ uv run pytest .
```

### Design decisions and constraints (first release)

- Supported input formats: only `*.cbz` files.
- Source archives behavior: archives are moved (`mv`) into the volume directory and kept after extraction.
- `ComicInfo.xml` presence: every input `.cbz` **must** contain a `ComicInfo.xml`; otherwise the script raises a specific error and exits.
- Naming conventions: the script will accept multiple input filename patterns to detect chapter numbers (e.g. `Chapter 1.cbz`, `Chapter 001.cbz`, `Ch.1.cbz`, `Chapter 100 Name.cbz`), but output folders will follow a uniform naming scheme.
- Volume directory name: `[series name] vNN` (e.g. `Berserk v01`). Volumes 1–9 are zero-padded (`v01`..`v09`).
- Chapter ranges: `--chapter-range` accepts non-contiguous ranges (e.g. `1,3,5..8`).
- Extraction: extraction behavior is left as a TODO in the code; currently if a non-standard archive structure is detected the script raises a specific error and exits so you can decide the desired behavior.
- Concurrency: default `--nb-worker` is `1`. Implementation will use `concurrent.futures.ProcessPoolExecutor`.
- Useful CLI flags: `--dry-run`, `--verbose`, `--force` (to overwrite existing directories).
- CLI: implemented with `argparse`.

- Extracted chapter directories are created inside the volume directory (i.e. `./[series] vNN/Chapter 001/`).
- Output chapter folder format: zero-padded 3 digits (e.g. `Chapter 001`).
- Missing chapter behavior: if a requested chapter is not present, the script errors and exits.
- Duplicate matches: if multiple archives match the same chapter number, the script errors and exits.

Expected behavior

- For each chapter selected by the range, the script will:
	- verify that the `.cbz` contains `ComicInfo.xml` (or exit with an error),
	- create the volume directory `[series] vNN` if needed (if the volume directory already exists the script will warn and continue),
	- move the `.cbz` archive into the volume directory,
	- extract the archive into a uniformly named chapter subdirectory inside the volume directory (e.g. `Berserk v01/Chapter 001`).

Behavior for existing destinations:
	- If the volume directory exists: the script yields a warning and processes chapters inside it.
	- If a chapter directory already exists: the script yields a warning and skips that chapter unless `--force` is provided, in which case the chapter directory is replaced.

### TODOs and current limitations

- Fine-grained handling of internal archive structures (flatten vs keep subfolders): TODO — the script will raise a specific error for unhandled cases.
- Merging or creating a volume-level `ComicInfo.xml`: handled later by a dedicated tool.

### cli

Main options
- `--path`: path to the root directory containing source `.cbz` files.
- `--dest`: destination root (defaults to `--path`) where the volume directory will be created.
- `--serie`: series name (used to name the volume directory). It is optional on the CLI — a `serie` key may instead be provided in `packer.json` in the source directory.
- `--volume`: volume number to create.
- `--chapter-range`: chapter range (e.g. `1..12`, `1,3,5..8`).
- `--nb-worker`: number of workers (default `1`).
- `--dry-run`: simulate actions without changing the filesystem.
- `--verbose`: verbose logging.
- `--force`: overwrite destination directories if necessary.
- Named patterns: use `--pattern` to select a named filename pattern (e.g., `mashle`, `fma`) which affects how main chapters and extras are detected.
- Batch files: supply `--batch-file <path>` or place a `.batch` file in the source directory (one CSV per line: `vol, chapters` e.g. `v01,1..8`).
- Per-path config: place a `packer.json` file in the `--path` directory to provide defaults (supported keys: `pattern`, `chapter_regex`, `extra_regex`, `nb_worker`, `batch_file`). **If present, `packer.json` must be valid JSON; parsing failures will cause the CLI to error and exit.** CLI args always override config values.


TODO: add tests doc (aka `uv run pytest packer`)

The initial version will include unit tests and runnable examples. Unit tests will be placed under `/packer/tests`.

Immediate roadmap
- Rework `packer/main.py` (split into subfiles, refine processing & find bugs).
- Test existing series
  - mashle
  - FMA
  - Berserk
  - Boruto Blue Vortex
- Add unit tests for `ComicInfo.xml` detection and chapter-range parsing.
- Document error scenarios and advanced options.

### Examples

Build Berserk volume 1

```console
$ tree Serie_A
Serie_A
├── Chapter 1.cbz
├── Chapter 2.cbz
└── Chapter 3.cbz

$ uv run packer \
    --path ./Serie_A \
    --serie "Berserk" \
    --volume 1 \
    --chapter-range "1..10" \
    --nb-worker 2

$ tree Serie_A
Serie_A
└── Berserk v01
    ├── Chapter 1.cbz
    ├── Chapter 1
    │   ├── 001.jpg
    │   ├── 002.jpg
    │   ├── 003.jpg
    │   └── ComicInfo.xml
    ├── Chapter 2.cbz
    ├── Chapter 2
    │   ├── 001.jpg
    │   ├── 002.jpg
    │   ├── 003.jpg
    │   └── ComicInfo.xml
    ├── Chapter 3.cbz
    └── Chapter 3
        ├── 001.jpg
        ├── 002.jpg
        ├── 003.jpg
        └── ComicInfo.xml
```
Run in dry-run

```consle


$ uv run packer \
    --path ./Serie_A \
    --serie "Berserk" \
    --volume 1 \
    --chapter-range "1,3,5..8" \
    --nb-worker 4 \
    --verbose \
    --dry-run
```

Batch volumes example

```console
# Build volume 1 (chapters 1..3) and volume 2 (chapters 4..6) in sequence
$ uv run packer \
    --path ./Serie_A \
    --serie "BatchSerie" \
    --batch "v01:1..3-v02:4..6" \
    --nb-worker 4
```

### Tests 

Tests are managed via `pytest`. Run the full suite locally with:

```console
$ uv run pytest packer -q
```

### Conversion & Calibre metadata

When generating EPUB/Kepub files for use with Calibre (or other e-book managers), embedded metadata is far more reliable than filename parsing alone. Suggestions to maximize metadata discovery:

Convertor CLI

A small `convertor` helper is available to convert existing volume directories into `.kepub.epub` files using Kindle Comic Converter (KCC):

```console
$ python -m convertor.cli <root-dir> [--force-regen] [--dry-run]
```

For each immediate subdirectory under `<root-dir>` a file named `<VolumeDir>.kepub.epub` is generated next to it unless it already exists (use `--force-regen` to override).

The convertor defaults match common KCC settings used for manga (Manga mode, Stretch/Upscale, Color mode, Cropping mode) and targets the Kobo "Libra Colour" profile by default.


- Preferred output filename: `<Serie> vNN.kepub.epub` (e.g. `Berserk v01.kepub.epub`) — keep the filename simple and use embedded metadata for rich fields.
- Embed the following EPUB metadata inside the generated file (these map well to Calibre's import heuristics):
  - `title`: `<Serie> vNN` or the volume title when present
  - `series`: `<Serie>` (populate `series_index` with `NN`)
  - `authors`: list of authors/creators
  - `identifier`: ISBN when available, otherwise a generated UUID/URN
  - `publisher` and `date` (release date) when known
  - `language` and optional `tags`/`subjects` when available
- Allow metadata overrides from `packer.json` via keys such as `serie`, `volume_title`, `authors`, `isbn`, `date`, and `publisher`. The `convertor` package will use these to set EPUB metadata.
- Keep filenames simple and machine-friendly (avoid special characters); rely on embedded metadata to convey rich information to Calibre.

Note: Calibre extracts metadata both from filenames and from embedded metadata inside the EPUB; embedding comprehensive metadata ensures best results across different cataloging policies.

Doctests for regex helpers are run as part of the test suite (`tests/test_core_doctest.py`).

Coverage

To measure test coverage we use `pytest-cov` (adds `--cov` support to pytest). Install it as a dev dependency:

```console
$ uv add --dev pytest-cov
```

Then run coverage (terminal report):

```console
$ make -C packer test-coverage
# or directly
$ uv run pytest packer --cov=packer --cov-report=term-missing
```

HTML report (opens at `htmlcov/index.html` after running):

```console
$ make -C packer coverage-html
```

### Developer notes

- Logging: use `--loglevel` to control verbosity (choices: `DEBUG`, `INFO`, `WARNING`/`WARN`, `ERROR`, `CRITICAL`). Use `--verbose` as a shorthand to enable `DEBUG` only when `--loglevel` is not provided.
- Named patterns: `--pattern` accepts `mashle` and `fma` to match known filename styles and extras (e.g., `Ch.013.5` or `Chap 16.1`). Use `--chapter-regex` and `--extra-regex` to override patterns at runtime when necessary.
- Running the CLI in a script context: invoking `src/packer/main.py` directly works; the entrypoint shim adjusts `sys.path` so imports succeed.

Quick examples:

- FMA extras (Chap 16.1, Chap 16.2) — both are associated with chapter 16 and extras are processed in numeric order:

```console
$ uv run packer \
  --path ./FMA_series \
  --serie "FMA" \
  --volume 1 \
  --chapter-range "16" \
  --pattern fma
```

- Batch multiple volumes:

```console
$ uv run packer \
  --path ./Shelf \
  --serie "BatchSerie" \
  --batch "v01:1..3-v02:4..6" \
  --nb-worker 4
```

If you're contributing, please add unit tests under `packer/tests` and run the full test suite before creating a PR.


### TODO

- [x] handle extra chapters / volume extra
- [x] pass an array `[volume:chapter range]
- [x] better logs
- [x] split into sub-files
- [ ] what to do if .cbz contain sub-dir ?
- [ ] handle chapters 0 / chapter A..Z
- [ ] rework readme