import zipfile

from packer.core import (
    find_cbz_files,
    has_comicinfo,
    map_chapters_to_files,
    parse_range,
)


def test_parse_range_simple():
    assert parse_range("1..3") == [1, 2, 3]
    assert parse_range("1,3,5..6") == [1, 3, 5, 6]


def test_has_comicinfo_true(tmp_path):
    p = tmp_path / "c1.cbz"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("ComicInfo.xml", "<xml></xml>")
    assert has_comicinfo(str(p))


def test_has_comicinfo_false(tmp_path):
    p = tmp_path / "c2.cbz"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("readme.txt", "no comicinfo")
    assert not has_comicinfo(str(p))


def test_find_and_map(tmp_path):
    # create sample files
    f1 = tmp_path / "Chapter 1.cbz"
    f2 = tmp_path / "Ch.2.cbz"
    f3 = tmp_path / "Chapter 10 Name.cbz"
    for f in (f1, f2, f3):
        with zipfile.ZipFile(f, "w") as z:
            z.writestr("ComicInfo.xml", "<xml/>")

    files = find_cbz_files(str(tmp_path))
    mapping = map_chapters_to_files(files)
    assert 1 in mapping
    assert 2 in mapping
    assert 10 in mapping
