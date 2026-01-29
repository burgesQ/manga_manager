Convertor
=========

Small helper to convert volume directories (extracted images) into `*.kepub.epub` files using Kindle Comic Converter (KCC).

Usage (from repository root):

```console
$ uv run convertor <root-dir-containing-volume-dirs>
```

Behavior:
- For each immediate subdirectory of `<root-dir>`, a file named `<VolumeDir>.kepub.epub` is created next to it.
- Existing files are skipped unless `--force-regen` is passed.
- Sensible KCC options for the device

Notes:
- The adapter prefers to run KCC as a module; if KCC is not installed it will try to call the `kcc` CLI.
- For testing, the convertor package includes unit tests that mock the conversion step.


- [ ] parallelize worker (1 worker = 1 epub)
- [ ] add some kind of force / reconvert
- [ ] refine trigger
      Now is: For each immediate subdirectory ...
      Should be: For each immediate subdirectory identified by convertor.json with no matching `*.kepub.epub`
