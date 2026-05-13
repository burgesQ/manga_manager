# convertor

Converts volume directories into `.kepub.epub` files using [KindleComicConverter (KCC)](https://github.com/ciromattia/kcc).

See the [root README](../README.md) for the full workflow and KCC settings reference.

---

## Quick start

```console
# Convert all volume directories under a root folder
uv run convertor ./Berserk

# Regenerate even if output already exists
uv run convertor ./Berserk --force-regen

# Dry run
uv run convertor ./Berserk --dry-run --verbose
```

For each subdirectory under `<root>`, convertor creates a `<VolumeDir>.kepub.epub` sibling file:

```
Berserk/
├── Berserk v01/              ← input dir
│   ├── Chapter 001/
│   └── ...
├── Berserk v01.kepub.epub    ← generated output
```

---

## KCC settings

All settings default to the recommended Kobo manga profile. Override only what you need:

| Flag | Default | Description |
|---|---|---|
| `--profile` | `KoLC` | KCC device profile (`KoLC` = Kobo Libra Colour) |
| `--[no-]manga-style` | on | Right-to-left reading direction |
| `--[no-]hq` | on | High-quality mode |
| `--[no-]forcecolor` | on | Force colour output |
| `--rotation 0-3` | `2` | 0=none, 1=90CW, 2=90CCW, 3=180° |
| `--cropping 0-2` | `2` | 0=off, 1=safe, 2=aggressive |

```console
uv run convertor ./Berserk --profile KoF --no-manga-style --rotation 0
```

---

## Cover image

If `cover.webp` exists at the root of a volume directory, convertor automatically inserts it as the first page before invoking KCC:

```
Berserk v01/
├── cover.webp        ← becomes the EPUB cover
├── Chapter 001/
└── ...
```

---

## KCC execution strategy

The adapter first tries KCC as a Python module (`kindlecomicconverter`). If that fails, it falls back to calling the `kcc-c2e` or `kcc` executables on `PATH`.

---

## Tests

```console
uv run pytest convertor -q
```
