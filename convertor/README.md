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

### Presets: manga vs comic

`--preset` selects the base KCC settings (default: `manga`):

| Preset | Reading direction | `--manga-style` | Colour | Other settings |
|---|---|---|---|---|
| `manga` (default) | right-to-left | on | on | `KoLC`, hq, rotation 2, cropping 2, upscale |
| `comic` | left-to-right | off | on | same as `manga` |

```console
# Western comics: colour, read left-to-right
uv run convertor ./Saga --preset comic
```

The effective direction is logged at INFO, e.g.
`Reading direction: left-to-right (comic preset)`.

### Individual flags

Every flag below is optional. A flag you leave out takes its value from the
preset; a flag you pass **always overrides the preset**:

| Flag | Preset default | Description |
|---|---|---|
| `--preset {manga,comic}` | `manga` | Base settings (see above) |
| `--profile` | `KoLC` | KCC device profile (`KoLC` = Kobo Libra Colour) |
| `--[no-]manga-style` | on (`manga`) / off (`comic`) | Right-to-left reading direction |
| `--[no-]hq` | on | High-quality mode |
| `--[no-]forcecolor` | on | Force colour output |
| `--rotation 0-3` | `2` | 0=none, 1=90CW, 2=90CCW, 3=180° |
| `--cropping 0-2` | `2` | 0=off, 1=safe, 2=aggressive |
| `--[no-]upscale` | on | Upscale images smaller than the device resolution |
| `--[no-]blackborders` | off | Fill border bands with black instead of white |

```console
# Manga preset, but a different device and no rotation
uv run convertor ./Berserk --profile KoF --rotation 0

# Comic preset, but force right-to-left anyway (the explicit flag wins)
uv run convertor ./Saga --preset comic --manga-style
```

The presets are also importable: `from convertor import PRESETS`
(`dict[str, KCCSettings]`).

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
