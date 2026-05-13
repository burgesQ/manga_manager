# packer

Groups `.cbz` chapter archives into a volume directory and extracts each into a `Chapter NNN/` subdirectory.

See the [root README](../README.md) for the full workflow, all CLI options, and examples.

---

## Quick start

```console
uv run packer \
  --path ./Berserk \
  --serie "Berserk" \
  --volume 1 \
  --chapter-range "1..12"
```

## Batch mode

```console
# Inline: build volume 1 (ch 1–12) and volume 2 (ch 13–24) in one run
uv run packer \
  --path ./Berserk \
  --serie "Berserk" \
  --batch "v01:1..12-v02:13..24"

# From a file (one line per volume: v01,1..12)
uv run packer --path ./Berserk --serie "Berserk" --batch-file berserk.batch

# Auto-discovery: place a .batch file in --path; packer picks it up automatically
```

## Named patterns

Pre-configured regex patterns for common download sources:

| `--pattern` | Matches | Source |
|---|---|---|
| `default` | `Chapter 001`, `Ch.001` | Generic |
| `mangafox` | `Ch.013`, `Ch.013.5` | MangaFox / Tachiyomi |
| `mangafire` | `Chap 013`, `Chap 013.5` | MangaFire |
| `animeSama` | `Chapitre 013` | animesama.fr |

## packer.json

Place in `--path` to set per-directory defaults (CLI flags always override):

```json
{
  "serie": "Berserk",
  "pattern": "mangafox",
  "nb_worker": 2,
  "batch_file": "berserk.batch",
  "covers": { "1": "cover_v01.webp" }
}
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `2` | CLI / argument error |
| `3` | Missing chapter |
| `4` | Duplicate chapter match |
| `6` | Processing error |

## Tests

```console
uv run pytest packer -q
uv run pytest packer --cov=packer --cov-report=term-missing
```
