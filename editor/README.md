# editor

Injects, dumps, and clears EPUB metadata from YAML files. Supports a single `.epub` file or a directory of EPUBs.

See the [root README](../README.md) for the full metadata YAML format and field reference.

---

## Subcommands

### `inject` — write metadata into EPUBs

```console
uv run editor inject <path> <metadata.yaml> [--force] [--dry-run]

# Examples
uv run editor inject ./Berserk berserk.yaml
uv run editor inject "./Berserk v01.epub" berserk.yaml --force
uv run editor inject ./Berserk berserk.yaml --dry-run --verbose
```

| Option | Description |
|---|---|
| `--force` | Overwrite metadata if it already exists |
| `--dry-run` | Simulate without writing |

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
