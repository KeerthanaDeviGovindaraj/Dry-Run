"""
Unit tests for the grounding module. No API calls.

Run:  PYTHONPATH=src .venv/bin/python tests_grounding.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dryrun import grounding
from dryrun.grounding import MAX_CHARS


def test_from_text_basic():
    g = grounding.from_text("activation rate: 38%", label="metrics")
    assert not g.is_empty()
    assert not g.truncated
    assert g.label == "metrics"
    assert "given" in g.as_prompt_block()
    assert "activation rate: 38%" in g.as_prompt_block()


def test_empty_text():
    g = grounding.from_text("   ")
    assert g.is_empty()
    assert g.as_prompt_block() == ""


def test_truncation():
    big = "row\n" * (MAX_CHARS)          # well over the cap
    g = grounding.from_text(big)
    assert g.truncated
    assert len(g.text) <= MAX_CHARS + 20  # cap + truncation marker
    assert "[truncated]" in g.text


def test_from_file_csv():
    raw = b"feature,requests\nmobile,120\noffline,45\n"
    g = grounding.from_file("asks.csv", raw)
    assert "mobile,120" in g.text
    assert g.label == "asks.csv"


def test_from_file_rejects_binary_type():
    try:
        grounding.from_file("logo.png", b"\x89PNG")
        assert False, "should have rejected .png"
    except ValueError as e:
        assert "Unsupported file type" in str(e)


def test_from_file_latin1_fallback():
    raw = "café load: 50\n".encode("latin-1")
    g = grounding.from_file("notes.txt", raw)
    assert "load: 50" in g.text


def test_combine():
    fd = grounding.from_file("m.csv", b"x,y\n1,2\n")
    g = grounding.combine("extra note", fd)
    assert g is not None
    assert "m.csv" in g.label and "pasted" in g.label
    assert "1,2" in g.text and "extra note" in g.text


def test_combine_empty():
    assert grounding.combine("", None) is None
    assert grounding.combine("   ", None) is None


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"  ✓ {t.__name__}")
    print(f"\nALL {len(tests)} GROUNDING TESTS PASSED ✅")


if __name__ == "__main__":
    main()
