import json
from pathlib import Path

from packer.testing import make_cbz, run_packer


def test_serie_can_be_provided_via_packer_json(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    # provide serie via packer.json
    cfg = {"serie": "FromConfig"}
    (src / "packer.json").write_text(json.dumps(cfg))

    # create Chapter 1
    make_cbz(src, "Chapter 1.cbz")

    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--volume",
            "1",
            "--chapter-range",
            "1",
        ],
    )
    assert res.returncode == 0
    vol = src / "FromConfig v01"
    assert vol.exists()
    assert (vol / "Chapter 1.cbz").exists()
