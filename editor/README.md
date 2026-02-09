## editor

Small helper to manage EPUB files metadata with three main operations: inject, dump, and clear.

### Usage (from repository root)

#### Inject metadata into EPUBs

```console
# From a YAML metadata file
$ uv run editor inject <path> <metadata.yaml> [--force] [--dry-run]

# Examples
$ uv run editor inject ./volumes metadata.yaml
$ uv run editor inject ./volumes/Berserk v01.epub metadata.yaml --force
$ uv run editor inject ./volumes metadata.yaml --dry-run --verbose
```

#### Dump metadata from EPUBs

```console
# Extract metadata to a YAML file (or stdout)
$ uv run editor dump <path> [--output output.yaml] [--verbose]

# Examples
$ uv run editor dump ./volumes
$ uv run editor dump ./volumes/Berserk v01.epub --output meta.yaml
$ uv run editor dump ./volumes --output current_metadata.yaml --verbose
```

#### Clear metadata from EPUBs

```console
# Remove all custom metadata from EPUBs
$ uv run editor clear <path> [--dry-run] [--verbose]

# Examples
$ uv run editor clear ./volumes
$ uv run editor clear ./volumes/Series v01.epub --dry-run
$ uv run editor clear ./volumes --verbose
```

### File or Directory Support

All three subcommands (`inject`, `dump`, `clear`) support:
- **Single EPUB file**: `path/to/file.epub`
- **Directory**: `path/to/directory/` (processes all `.epub` files within)

### CLI Options

**Common options (all subcommands)**:
- `--verbose`: Enable verbose logging
- `-l, --loglevel`: Set explicit log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

**inject-specific**:
- `--force`: Overwrite existing metadata
- `--dry-run`: Simulate without making changes

**dump-specific**:
- `-o, --output`: Output YAML file (default: print to stdout)

**clear-specific**:
- `--dry-run`: Simulate without making changes

### Supported Metadata

#### ✅ Standard Dublin Core

- `dc:title` → Title
- `dc:creator` → Author(s)
- `dc:identifier` (with id="isbn") → ISBN
- `dc:publisher` → Publisher
- `dc:language` → Language
- `dc:date` → Publication date
- `dc:description` → Description/Summary

#### ✅ Calibre Custom Metadata

- `calibre:series` → Series name
- `calibre:series_index` → Position in series
- `calibre:rating` → Rating
- `calibre:tags` → Tags

### YAML Metadata Format Example

```yaml
series: "Berserk"
author: "Kentaro Miura"
title: "Berserk v01"
isbn: "978-1-56931-900-0"
publisher: "Dark Horse Comics"
language: "en"
date: "2003-08-19"
description: "The dark fantasy manga classic"
tags:
  - manga
  - dark-fantasy
  - seinen
```

### Test Suite

Run tests from repository root:

```console
$ uv run pytest editor -q
```
