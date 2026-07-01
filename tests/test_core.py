"""Unit tests for the pure/core functions of the Tag Creator.

These exercise the hardware-free logic (color parsing, float parsing, CSV
intake, per-line text mapping) and the PDF generator invariants (page count ==
row count, empty-CSV guard, hole variants). No GUI is instantiated.
"""
import re

import pytest


def _page_count(pdf_path):
    with open(str(pdf_path), "rb") as f:
        data = f.read()
    # reportlab writes one "/Type /Page" object per page (the pages tree node is
    # "/Type /Pages", which the trailing word boundary excludes).
    return len(re.findall(rb"/Type\s*/Page\b", data))


def _make_csv(tmp_path, rows, sep=","):
    header = sep.join(["Line1", "Line2"])
    body = ["%s%s%s" % ("v%d" % i, sep, "w%d" % i) for i in range(rows)]
    p = tmp_path / "data.csv"
    p.write_text("\n".join([header] + body) + "\n", encoding="utf-8")
    return str(p)


# --------------------------------------------------------------------------
# parse_hex_color
# --------------------------------------------------------------------------
def test_parse_hex_color_valid(tag):
    assert tag.parse_hex_color("#ffffff") == (1.0, 1.0, 1.0)
    assert tag.parse_hex_color("#000000") == (0.0, 0.0, 0.0)


def test_parse_hex_color_three_digit_expands(tag):
    assert tag.parse_hex_color("#abc") == tag.parse_hex_color("#aabbcc")


def test_parse_hex_color_invalid_digits_fall_back_to_black(tag):
    # Regression: previously raised ValueError instead of the documented fallback.
    assert tag.parse_hex_color("#GGGGGG") == (0.0, 0.0, 0.0)
    assert tag.parse_hex_color("#zz") == (0.0, 0.0, 0.0)


def test_parse_hex_color_wrong_length_falls_back_to_black(tag):
    assert tag.parse_hex_color("") == (0.0, 0.0, 0.0)
    assert tag.parse_hex_color("#12345") == (0.0, 0.0, 0.0)


# --------------------------------------------------------------------------
# _to_float
# --------------------------------------------------------------------------
def test_to_float(tag):
    assert tag._to_float("1.5") == 1.5
    assert tag._to_float("  2  ") == 2.0
    assert tag._to_float("") == 0.0
    assert tag._to_float(None) == 0.0
    assert tag._to_float("not-a-number") == 0.0


# --------------------------------------------------------------------------
# robust_read_csv
# --------------------------------------------------------------------------
@pytest.mark.parametrize("sep", [",", ";", "\t"])
def test_robust_read_csv_infers_delimiter(tag, tmp_path, sep):
    p = tmp_path / "in.csv"
    p.write_text("Line1%sLine2\nA%sB\n" % (sep, sep), encoding="utf-8")
    df = tag.robust_read_csv(str(p))
    assert list(df.columns) == ["Line1", "Line2"]
    assert len(df) == 1


def test_robust_read_csv_strips_bom(tag, tmp_path):
    p = tmp_path / "bom.csv"
    p.write_text("Line1,Line2\nA,B\n", encoding="utf-8-sig")
    df = tag.robust_read_csv(str(p))
    assert list(df.columns) == ["Line1", "Line2"]


# --------------------------------------------------------------------------
# pick_text_for_line
# --------------------------------------------------------------------------
def test_pick_text_for_line_explicit_mapping(tag, tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("Name,Line2\nAlice,Bob\n", encoding="utf-8")
    df = tag.robust_read_csv(str(p))
    row = df.iloc[0]
    assert tag.pick_text_for_line(df, row, 0, "Name") == "Alice"


def test_pick_text_for_line_name_variant(tag, tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("Name,Line2\nAlice,Bob\n", encoding="utf-8")
    df = tag.robust_read_csv(str(p))
    row = df.iloc[0]
    # line index 1 -> "Line2" column present via <auto>
    assert tag.pick_text_for_line(df, row, 1, "<auto>") == "Bob"


def test_pick_text_for_line_positional_fallback(tag, tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("Name,Other\nAlice,Bob\n", encoding="utf-8")
    df = tag.robust_read_csv(str(p))
    row = df.iloc[0]
    # No Line1 column and unknown selection -> positional (index 0)
    assert tag.pick_text_for_line(df, row, 0, "<auto>") == "Alice"
    assert tag.pick_text_for_line(df, row, 0, "Missing") == "Alice"


def test_pick_text_for_line_missing_value_returns_empty(tag, tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("Line1,Line2\nAlice,\n", encoding="utf-8")
    df = tag.robust_read_csv(str(p))
    row = df.iloc[0]
    assert tag.pick_text_for_line(df, row, 1, "<auto>") == ""


def test_pick_text_for_line_out_of_range_returns_empty(tag, tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("Line1,Line2\nAlice,Bob\n", encoding="utf-8")
    df = tag.robust_read_csv(str(p))
    row = df.iloc[0]
    assert tag.pick_text_for_line(df, row, 5, "<auto>") == ""


# --------------------------------------------------------------------------
# generate_labels
# --------------------------------------------------------------------------
@pytest.mark.parametrize("rows", [1, 2, 4])
def test_generate_labels_page_count_matches_rows(tag, tmp_path, rows):
    csv = _make_csv(tmp_path, rows)
    out = tmp_path / "out.pdf"
    tag.generate_labels(csv, str(out), [12, 12], [0, 0],
                        label_width_in=6, label_height_in=3)
    assert _page_count(out) == rows


def test_generate_labels_rejects_empty_csv(tag, tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("Line1,Line2\n", encoding="utf-8")  # header only
    out = tmp_path / "empty.pdf"
    with pytest.raises(ValueError):
        tag.generate_labels(str(p), str(out), [12, 12], [0, 0],
                            label_width_in=6, label_height_in=3)


def test_generate_labels_rejects_nonpositive_label_size(tag, tmp_path):
    csv = _make_csv(tmp_path, 1)
    out = tmp_path / "bad.pdf"
    with pytest.raises(ValueError):
        tag.generate_labels(csv, str(out), [12], [0],
                            label_width_in=0, label_height_in=3)


@pytest.mark.parametrize("holes", [2, 4])
def test_generate_labels_with_holes(tag, tmp_path, holes):
    csv = _make_csv(tmp_path, 2)
    out = tmp_path / ("holes_%d.pdf" % holes)
    tag.generate_labels(csv, str(out), [12, 12], [0, 0],
                        holes_enabled=True, holes_count=holes,
                        hole_diameter_in=0.2, hole_edge_margin_in=0.1,
                        label_width_in=6, label_height_in=3)
    assert _page_count(out) == 2


# --------------------------------------------------------------------------
# metadata invariants
# --------------------------------------------------------------------------
def test_version_and_title_present(tag):
    assert isinstance(tag.__version__, str) and tag.__version__
    assert tag.APP_TITLE == "Automated Tag Creator V5 by LxveAce"
