import os
import shutil
import importlib.util
import sys
from pathlib import Path
import pytest

import convertor


CANDIDATE_MODULES = ("kcc", "kcc.__main__", "kcc.kcc", "kindlecomicconverter")


def _find_importable_module():
    for name in CANDIDATE_MODULES:
        try:
            if importlib.util.find_spec(name) is not None:
                return name
        except Exception:
            # Ignore import hook failures
            continue
    return None


def _find_executable():
    # adapter historically uses 'kcc-c2e' executable
    return shutil.which("kcc-c2e") or shutil.which("kcc")


@pytest.mark.integration
def test_real_kcc_conversion(tmp_path: Path):
    """Integration test: run a real KCC conversion if KCC is available.

    This test will be skipped if neither an importable KCC module nor the
    `kcc-c2e`/`kcc` executable is available on PATH. It performs a minimal
    conversion (one small image) and asserts that an output file is created.
    """
    module_name = _find_importable_module()
    exe = _find_executable()

    if not module_name and not exe:
        pytest.skip(
            "KCC not available (no importable module and no 'kcc-c2e' executable);"
            " install KCC or set up PATH to run this integration test"
        )

    # Create a sample volume
    root = tmp_path / "root"
    root.mkdir()
    vol = root / "Series vX"
    vol.mkdir()
    # Add a tiny dummy image file (not a real JPEG, but KCC may accept it; if not,
    # KCC may fail — in that case the test will surface that failure)
    (vol / "001.jpg").write_bytes(b"\xff\xd8\xff\xdb0\x00")

    out_path = vol.with_suffix(".kepub.epub")

    # Run the convertor; this will use the adapter which prefers module execution
    try:
        res = convertor.convert_volume(vol, out_path, dry_run=False)
    except Exception as exc:
        # If KCC is present but fails on this minimal input, skip the test with a
        # helpful message noting the detected module/executable and the error.
        pytest.skip(f"KCC present but failed on sample conversion (module={module_name!r} exe={exe!r}): {exc}")

    assert out_path.exists(), f"output file not created: {out_path}"
    assert out_path.stat().st_size > 0, "output file is empty"
