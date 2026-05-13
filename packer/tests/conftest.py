import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from packer.config import Config


@pytest.fixture
def run_packer():
    def _run_packer(tmp_path: Path, args):
        script = Path(__file__).resolve().parents[1] / "src" / "packer" / "main.py"
        cmd = [sys.executable, str(script)] + args
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res

    return _run_packer


@pytest.fixture
def make_cbz():
    def _make_cbz(path: Path, name: str, include_comicinfo: bool = True):
        p = path / name
        with zipfile.ZipFile(p, "w") as z:
            if include_comicinfo:
                z.writestr("ComicInfo.xml", "<ComicInfo></ComicInfo>")
            z.writestr("001.jpg", "img")
        return p

    return _make_cbz


@pytest.fixture
def make_config():
    def _make_config(
        src: Path,
        dest: Path | None = None,
        *,
        serie: str = "Manga",
        volume: int = 1,
        chapter_range: list[int] | None = None,
        nb_worker: int = 1,
        **kwargs,
    ) -> Config:
        return Config(
            path=str(src),
            dest=str(dest or src),
            serie=serie,
            volume=volume,
            chapter_range=chapter_range or [1],
            nb_worker=nb_worker,
            **kwargs,
        )

    return _make_config
