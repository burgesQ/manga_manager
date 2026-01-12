# manga_creator

A collection of small scripts to help manage a manga library (target: Kobo).

This repository currently contains a `packer` utility that groups chapter
archives into volume directories.

Overview
- Language: Python (standard library only for now)
- Target platform: Linux (tested on Linux Mint 22.3 / Debian 13)

All package are managed with `uv` (TODO: add link & few example)

## TODO

- [ ] finish packer
- [ ] comic info edit
- [ ] epub builder (kindle comic convertor <3)
- [ ] calibre sync !?


## TLDR

```console
$ uv run packer --dry-run --loglevel INFO \
    --path ~/Shelf/MASHLE/ \
    --pattern=mashle \
    --serie "Mashle" \
    --batch "v01:1..8-v02:9..17-v03:18..26-v04:27..35-v05:36..44-v06:45..53-v07:54..62-v08:63..72"
```
