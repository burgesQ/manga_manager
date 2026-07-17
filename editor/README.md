# editor

Injects, dumps, and clears EPUB metadata from YAML files. Supports a single `.epub` file or a directory of EPUBs.

See the [root README](../README.md) for the full metadata YAML format and field reference.

---

## Subcommands

### `inject` — write metadata into EPUBs

```console
uv run editor inject <path> <metadata.yaml> [--force] [--dry-run] [--chapters chapters.yaml]

# Examples
uv run editor inject ./Berserk berserk.yaml
uv run editor inject "./Berserk v01.epub" berserk.yaml --force
uv run editor inject ./Berserk berserk.yaml --dry-run --verbose
uv run editor inject ./JJKM jjkm.yaml --chapters chapters_jjkm.yaml
```

| Option | Description |
|---|---|
| `--force` | Overwrite metadata if it already exists |
| `--dry-run` | Simulate without writing |
| `--locale` | Locale block (`english`/`japanese`/`french`) for publisher, ISBN, and release date |
| `--chapters` | Optional chapters YAML; relabels the EPUB table-of-contents entries with chapter titles |

#### Chapter titles

KCC names each `Chapter NNN` folder verbatim in the generated EPUB table of contents.
Chapter-title injection relabels those TOC entries to `Chapter NNN - <title>` (e.g.
`Chapter 001 - Special Grade Incident`). Matching is by chapter **number** parsed from the
existing TOC label, so titles land in the right entry regardless of which volume EPUB is
processed. Entries with no matching number (the `Chapter 000` cover, numbered extras) are
left untouched. TOC relabelling runs even when metadata injection is skipped
(already present); it is honoured under `--dry-run`.

The chapter titles are read from the first available source (highest precedence first):

1. `--chapters <file>` — CLI flag (always wins)
2. `chapters_file: ./path.yaml` key in the metadata YAML — a path resolved **relative to
   the metadata file**, so no CLI flag is needed
3. `chapters:` list inlined directly in the metadata YAML — everything in one file

> There is no portable way for one YAML file to `!include` another with `yaml.safe_load`,
> so use `chapters_file:` (external file) or an inline `chapters:` list instead.

Chapters YAML shape (reuses `metadatas/chapters_*.yaml`; the same `chapters:` block also
works inlined in the metadata file):

```yaml
series: "Jujutsu Kaisen Modulo"   # optional, ignored
chapters:
  - number: 1
    title: "Special Grade Incident"
    volume: 1                     # optional, ignored
  - number: 2
    title: "Deterrence"
```

Metadata file pointing at an external chapters file:

```yaml
series: "Jujutsu Kaisen Modulo"
author: "Gege Akutami"
chapters_file: "./chapters_jjkm.yaml"   # no --chapters needed
volumes:
  - number: 1
```

### `dump` — extract metadata to YAML

```console
uv run editor dump <path> [--output file.yaml]

uv run editor dump ./Berserk                            # print to stdout
uv run editor dump ./Berserk --output current.yaml     # save to file
```

### `clear` — remove all custom metadata

```console
uv run editor clear <path> [--dry-run]
```

---

## Metadata YAML format

```yaml
series: "Berserk"
author: "Kentaro Miura"
publisher: "Dark Horse Comics"
language: "en"          # BCP 47; default "en-US" if omitted

volumes:
  - number: 1
    title: "Black Swordsman"
    english:
      isbn: "978-1-56931-900-0"
      release_date: "2003-08-19"
  - number: 2
    title: "The Shadow"
    language: "fr"      # per-volume override
    english:
      isbn: "978-1-56931-980-2"
      release_date: "2004-01-01"
```

See `metadatas/` for real-world examples.

---

## Tests

```console
uv run pytest editor -q
```
