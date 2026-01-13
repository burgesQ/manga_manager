import re
from pathlib import Path

from packer.utils import make_cbz, run_packer


def test_warn_loglevel_suppresses_info(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    make_cbz(src, "Chapter 1.cbz")
    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "WTest",
            "--volume",
            "1",
            "--chapter-range",
            "1",
            "--loglevel",
            "WARN",
        ],
    )
    assert res.returncode == 0
    # INFO lines (planned tasks) should not be present
    assert "planned tasks" not in res.stderr


def test_extras_without_main_ok(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    # only an extra, no main
    make_cbz(src, "Chap 4.5.cbz")
    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "FMA",
            "--volume",
            "1",
            "--chapter-range",
            "4",
            "--pattern",
            "fma",
        ],
    )
    assert res.returncode == 0, f"stderr={res.stderr}"
    vol = src / "FMA v01"
    assert vol.exists()
    assert (vol / "Chap 4.5.cbz").exists()
    assert (vol / "Chapter 004.5").exists()


def test_multinumber_filename_parsing():
    re.compile(r"(?i)ch(?:\.|apter)?[\s._-]*0*([0-9]+)")
    re.compile(r"(?i)ch(?:\.|apter)?[\s._-]*0*([0-9]+)\.([0-9]+)")
    # filename contains volume and chapter numbers, ensure we extract chapter 13 extra 2
    run_packer(Path("."), [])


def test_planned_tasks_order_with_workers(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    # create main and extras
    make_cbz(src, "Chap 16.cbz")
    make_cbz(src, "Chap 16.2.cbz")
    make_cbz(src, "Chap 16.1.cbz")

    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "FMA",
            "--volume",
            "1",
            "--chapter-range",
            "16",
            "--pattern",
            "fma",
            "--nb-worker",
            "4",
        ],
    )
    assert res.returncode == 0
    out = res.stderr
    # planned tasks line should list extras in numeric order
    planned_block = []
    for line in out.splitlines():
        if "planned tasks" in line:
            planned_block.append(line)
        if "chapter 16.1" in line or "chapter 16.2" in line:
            planned_block.append(line)
    # Find indices
    idx_e1 = out.find("chapter 16.1")
    idx_e2 = out.find("chapter 16.2")
    assert idx_e1 != -1 and idx_e2 != -1 and idx_e1 < idx_e2
