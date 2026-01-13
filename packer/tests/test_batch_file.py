from pathlib import Path

from packer.utils import make_cbz, run_packer


def test_batch_file_parsing(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    # create chapters
    for i in range(1, 7):
        make_cbz(src, f"Chapter {i}.cbz")

    # create a batch file
    batch = src / ".batch"
    batch.write_text("v01,1..3\nv02,4..6\n")

    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "BatchFile",
            "--batch-file",
            str(batch),
        ],
    )
    assert res.returncode == 0
    # check that volume directories exist
    assert (src / "BatchFile v01").exists()
    assert (src / "BatchFile v02").exists()


def test_auto_discover_batch_file(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    # create chapters
    for i in range(1, 5):
        make_cbz(src, f"Chapter {i}.cbz")

    # create an auto-discovery .batch file
    batch = src / ".batch"
    batch.write_text("1,1..2\n2,3..4\n")

    res = run_packer(
        tmp_path,
        [
            "--path",
            str(src),
            "--serie",
            "AutoBatch",
        ],
    )
    assert res.returncode == 0
    assert (src / "AutoBatch v01").exists()
    assert (src / "AutoBatch v02").exists()
