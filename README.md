# manga_creator

A collection of small scripts to help manage a manga library (target: Kobo).

This repository currently contains a `packer` utility that groups chapter
archives into volume directories.

Overview
- Language: Python (standard library only for now)
- Target platform: Linux (tested on Linux Mint 22.3 / Debian 13)

All package are managed with `uv` (TODO: add link & few example)

## TODO

- [x] finish packer v1.0
- [ ] packer v1.1
  - [x] DRY things up
  - [ ] DRY things up (again)
  - [ ] simplify the code
  - [ ] get ride of the LLM' "foret de 'if'"
  - [ ] Inject ISBN, author and others ?
- [ ] convertor v1.0
  - [ ] convert to epub, take meta info somewhere
  - [x] epub builder (kindle comic convertor <3 aka https://github.com/ciromattia/kcc#usage)
  - [x] no GUI
- [ ] epub meta
  - [ ] edit meta from epub

- [ ] calibre sync !?
- [ ] update root readme for process (dl from Tachiyomi, move to host, run manga_creator script suites)
