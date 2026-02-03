from pathlib import Path

from packer.tests.conftest import make_cbz, run_packer


def test_named_pattern_mashle(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()

    make_cbz(src, "Ch.013.cbz")
    make_cbz(src, "Ch.013.5.cbz")

    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "Mashle",
            "--volume",
            "1",
            "--chapter-range",
            "13",
            "--pattern",
            "mashle",
        ],
    )
    assert res.returncode == 0, (
        f"packer failed: stdout={res.stdout} stderr={res.stderr}"
    )

    vol = src / "Mashle v01"
    assert vol.exists()
    assert (vol / "Ch.013.cbz").exists()
    assert (vol / "Ch.013.5.cbz").exists()


def test_custom_regex_override(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()

    make_cbz(src, "X_013.cbz")
    make_cbz(src, "X_014.cbz")

    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "Custom",
            "--volume",
            "1",
            "--chapter-range",
            "13..14",
            "--chapter-regex",
            r"(?i)X_0*([0-9]+)",
        ],
    )
    assert res.returncode == 0, (
        f"packer failed: stdout={res.stdout} stderr={res.stderr}"
    )

    vol = src / "Custom v01"
    assert vol.exists()
    assert (vol / "X_013.cbz").exists()
    assert (vol / "X_014.cbz").exists()
