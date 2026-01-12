# manga_creator

A collection of small scripts to help manage a manga library (target: Kobo).

This repository currently contains a `packer` utility that groups chapter
archives into volume directories.

Overview
- Language: Python (standard library only for now)
- Target platform: Linux (tested on Linux Mint 22.3 / Debian 13)

## packer

The `packer` purpose: for a given series, create a volume directory, move
chapter archives (`.cbz`) into it, and extract each archive into a chapter
subdirectory.

Design decisions and constraints (first release):

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

Expected behavior

- For each chapter selected by the range, the script will:
- verify that the `.cbz` contains `ComicInfo.xml` (or exit with an error),
- create the volume directory `[series] vNN` if needed,
- move the `.cbz` archive into the volume directory,
- extract the archive into a uniformly named chapter subdirectory (e.g. `Chapter 001`).

TODOs and current limitations

- Fine-grained handling of internal archive structures (flatten vs keep subfolders): TODO — the script will raise a specific error for unhandled cases.
- Merging or creating a volume-level `ComicInfo.xml`: handled later by a dedicated tool.

Usage examples

```console
$ tree Serie_A
Serie_A
├── Chapter 1.cbz
├── Chapter 2.cbz
└── Chapter 3.cbz

$ python -m packer.main \
--path ./Serie_A \
--serie "Berserk" \
--volume 1 \
--chapter-range "1..10" \
--nb-worker 1

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

$ python -m packer.main \
--path ./Serie_A \
--serie "Berserk" \
--volume 1 \
--chapter-range "1,3,5..8" \
--nb-worker 4 \
--verbose \
--dry-run
```

Main options
- `--path`: path to the root directory containing source `.cbz` files.
- `--dest`: destination root (defaults to `--path`) where the volume directory will be created.
- `--serie`: series name (used to name the volume directory).
- `--volume`: volume number to create.
- `--chapter-range`: chapter range (e.g. `1..12`, `1,3,5..8`).
- `--nb-worker`: number of workers (default `1`).
- `--dry-run`: simulate actions without changing the filesystem.
- `--verbose`: verbose logging.
- `--force`: overwrite destination directories if necessary.

Tests & examples

The initial version will include unit tests and runnable examples.

Immediate roadmap
- Implement `packer/main.py` (CLI + move/validation logic for `.cbz`).
- Add unit tests for `ComicInfo.xml` detection and chapter-range parsing.
- Document error scenarios and advanced options.
