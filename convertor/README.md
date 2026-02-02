Convertor
=========

Small helper to convert volume directories (extracted images) into `*.kepub.epub` files using Kindle Comic Converter (KCC).

Usage (from repository root):

```console
$ uv run convertor <root-dir-containing-volume-dirs>
```

 For each immediate subdirectory of `<root-dir>`, a file named `<VolumeDir>.kepub.epub` is created next to it (e.g. `Berserk v01.kepub.epub`).
 Existing files are skipped unless `--force-regen` is passed, which will attempt to remove the existing file before conversion.
 Defaults match KCC options visible in the UI: Manga mode, Stretch/Upscale, Color mode, Cropping mode, and target a Kobo profile by default.
- Sensible KCC options for the device

 The adapter first attempts to execute KCC as a Python module (tries multiple module names such as `kcc`, `kindlecomicconverter`, `KindleComicConverter`).
 If module invocation is not possible the adapter falls back to calling known CLI executables (`kcc-c2e`, `kcc`).
 If none of the candidates succeed the adapter raises a `subprocess.CalledProcessError` with the last process output attached.
Notes:
- The adapter prefers to run KCC as a module; if KCC is not installed it will try to call the `kcc` CLI.
 On platforms where KCC is installed via package manager or as a Python module, module-run may be preferred.
 Unit tests mock `runpy` and `subprocess.run` so they run reliably in CI and locally.

- [ ] parallelize worker (1 worker = 1 epub)
 `--force-regen`: force regeneration of existing output files (attempts to remove file first).
 `--dry-run`: only print planned actions without running conversion.
 `--nb-worker`: reserved (not used aggressively by KCC due to potential concurrency issues).
- [ ] add some kind of force / reconvert
