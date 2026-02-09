# manga_creator

A collection of small scripts to help manage a manga library (target: Kobo).

## Packages Overview

This repository contains three main utilities:

1. **packer** - Groups chapter archives (`.cbz`) into volume directories with extracted chapter subdirectories
2. **editor** - Manages EPUB metadata (inject, dump, clear) from single files or directories
3. **convertor** - Converts volume directories into `*.kepub.epub` files using Kindle Comic Converter (KCC)

## General Info

- Language: Python 3.12+
- Target platform: Linux (tested on Linux Mint 22.3 / Debian 13)
- Package manager: `uv`

## Quick Start

```console
# Test everything
$ uv run pytest .

# Pack volumes
$ uv run packer --path ./Manga/Series --serie "Series" --volume 1 --chapter-range "1..12"

# Manage EPUB metadata
$ uv run editor inject ./volumes metadata.yaml
$ uv run editor dump ./volumes --output metadata.yaml
$ uv run editor clear ./volumes

# Convert volumes to EPUB
$ uv run convertor ./volumes
```

## TODO

### packer v1.1
- [x] DRY things up
- [ ] DRY things up (again)
- [ ] simplify the code
- [ ] get ride of the LLM' "foret de 'if'"

### editor v1.0 ✅ (complete)
- [x] inject metadata into EPUBs (single file or directory)
- [x] dump metadata from EPUBs (single file or directory)
- [x] clear metadata from EPUBs (single file or directory)
- [x] support both file and directory paths for all operations
- [x] CLI with subcommands (inject, dump, clear)
- [x] dry-run support for all operations

### convertor v1.0
- [ ] parallelize workers (1 worker = 1 EPUB)
- [ ] add force/reconvert option

### Future enhancements
- [ ] calibre sync
- [ ] batch metadata file per volume
- [ ] batch metadata file per series
- [ ] update root readme with full workflow (dl from Tachiyomi → manga_creator suite)
