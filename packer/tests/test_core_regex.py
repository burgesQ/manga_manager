import re

from packer.core import _match_chapter, _match_extra, extract_chapter_number


def test_match_extra_and_chapter_helpers():
    ch_pat = re.compile(r"(?i)ch(?:\.|apter)?[\s._-]*0*([0-9]+)")
    ex_pat = re.compile(r"(?i)ch(?:\.|apter)?[\s._-]*0*([0-9]+)\.([0-9]+)")

    assert _match_chapter("Ch.013.cbz", ch_pat) == 13
    assert _match_extra("Ch.013.5.cbz", ex_pat) == (13, "5")

    # when extra matches we return only the extra
    assert extract_chapter_number(
        "Ch.013.5.cbz", chapter_pat=ch_pat, extra_pat=ex_pat
    ) == [(13, "5")]

    # chapter only
    assert extract_chapter_number(
        "Ch.013.cbz", chapter_pat=ch_pat, extra_pat=ex_pat
    ) == [(13, None)]


def test_legacy_patterns():
    assert extract_chapter_number("Chapter 4.5.cbz") == [(4, "5")]
    assert extract_chapter_number("Chapter 4.cbz") == [(4, None)]
    assert extract_chapter_number("Ch.8.cbz") == [(8, None)]
