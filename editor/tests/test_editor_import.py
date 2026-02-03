import pytest

pytest.importorskip("ebooklib")


def test_editor_module_importable():
    import editor.editor_full as ef

    assert hasattr(ef, "EPUBMetadata")
