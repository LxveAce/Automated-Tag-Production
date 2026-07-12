"""Regression tests from a verify-first adversarial audit of the Tag Creator.

Two batches of pure/core fixes (no GUI is instantiated):

TAG-1 csv-ingest:
  * literal NA-like cells ("NA", "NULL", "None", "N/A", "NaN") must print verbatim,
    not be silently blanked by pandas' default NA detection;
  * a classic Excel ANSI/cp1252 CSV (degree sign, accented name) must load instead of
    hard-failing on UnicodeDecodeError;
  * two headers that differ only by whitespace must dedupe, not collapse into a Series
    that crashes pick_text_for_line;
  * the delimiter sniffer must be quote-aware so a quoted comma in a header doesn't win.

TAG-2 config-io:
  * a shallow-copied default must not let the load-time pad loops mutate the module
    globals;
  * a save must be atomic and report real success/failure (no false "saved");
  * a corrupt settings.json must be backed up, not silently discarded.
"""
import json

import pytest


# --------------------------------------------------------------------------
# TAG-1 csv-ingest
# --------------------------------------------------------------------------
def test_csv_preserves_na_like_literals(tag, tmp_path):
    p = tmp_path / "na.csv"
    p.write_text("Line1,Line2\nNA,NULL\nNone,N/A\nOK,NaN\n", encoding="utf-8")
    df = tag.robust_read_csv(str(p))
    assert tag.pick_text_for_line(df, df.iloc[0], 0, "<auto>") == "NA"
    assert tag.pick_text_for_line(df, df.iloc[0], 1, "<auto>") == "NULL"
    assert tag.pick_text_for_line(df, df.iloc[1], 0, "<auto>") == "None"
    assert tag.pick_text_for_line(df, df.iloc[1], 1, "<auto>") == "N/A"
    assert tag.pick_text_for_line(df, df.iloc[2], 1, "<auto>") == "NaN"


def test_csv_blank_cell_still_empty(tag, tmp_path):
    # na_filter=False must not turn a genuinely empty cell into anything but "".
    p = tmp_path / "gap.csv"
    p.write_text("Line1,Line2\nAlice,\n", encoding="utf-8")
    df = tag.robust_read_csv(str(p))
    assert tag.pick_text_for_line(df, df.iloc[0], 1, "<auto>") == ""


def test_csv_cp1252_fallback(tag, tmp_path):
    p = tmp_path / "ansi.csv"
    p.write_bytes(("Line1,Line2\n" + "90\xb0 Bracket,Pe\xf1a\n").encode("cp1252"))
    df = tag.robust_read_csv(str(p))
    assert tag.pick_text_for_line(df, df.iloc[0], 0, "<auto>") == "90\xb0 Bracket"
    assert tag.pick_text_for_line(df, df.iloc[0], 1, "<auto>") == "Pe\xf1a"


def test_csv_duplicate_stripped_headers_do_not_crash(tag, tmp_path):
    # 'Part' and 'Part ' both strip to 'Part'; must dedupe instead of crashing
    # pick_text_for_line with an ambiguous-Series ValueError.
    p = tmp_path / "dup.csv"
    p.write_text("Part,Part \nA,B\n", encoding="utf-8")
    df = tag.robust_read_csv(str(p))
    assert list(df.columns) == ["Part", "Part.1"]
    assert tag.pick_text_for_line(df, df.iloc[0], 0, "Part") == "A"
    assert tag.pick_text_for_line(df, df.iloc[0], 0, "Part.1") == "B"


def test_sniff_quoted_comma_header_picks_real_delimiter(tag, tmp_path):
    # A semicolon file whose header carries a quoted comma must not sniff to comma.
    p = tmp_path / "q.csv"
    p.write_text('"Size, mm";Weight\n"10, x";5\n', encoding="utf-8")
    df = tag.robust_read_csv(str(p))
    assert list(df.columns) == ["Size, mm", "Weight"]
    assert len(df) == 1
    assert tag.pick_text_for_line(df, df.iloc[0], 0, "Size, mm") == "10, x"


@pytest.mark.parametrize("sep", [",", ";", "\t", "|"])
def test_sniff_basic_delimiters_still_work(tag, tmp_path, sep):
    p = tmp_path / "s.csv"
    p.write_text("Line1%sLine2\nA%sB\n" % (sep, sep), encoding="utf-8")
    df = tag.robust_read_csv(str(p))
    assert list(df.columns) == ["Line1", "Line2"]
    assert len(df) == 1


# --------------------------------------------------------------------------
# TAG-2 config-io
# --------------------------------------------------------------------------
def _point_settings_at(tag, monkeypatch, path):
    monkeypatch.setattr(tag, "_settings_path", lambda: str(path))


def test_save_load_roundtrip(tag, tmp_path, monkeypatch):
    p = tmp_path / "settings.json"
    _point_settings_at(tag, monkeypatch, p)
    s = tag.load_settings()                      # no file -> defaults
    s["label_width_in"] = 3.5
    s["num_lines"] = 3
    assert tag.save_settings(s) is True
    out = tag.load_settings()
    assert out["label_width_in"] == 3.5
    assert out["num_lines"] == 3


def test_load_settings_does_not_corrupt_module_defaults(tag, tmp_path, monkeypatch):
    # A pre-line_colors file (omits line_colors) with num_lines=6: the pad loop must
    # NOT grow the shared module-global default list via an aliased shallow copy.
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"num_lines": 6, "header_map": []}), encoding="utf-8")
    _point_settings_at(tag, monkeypatch, p)
    before = list(tag.DEFAULT_SETTINGS["line_colors"])
    out = tag.load_settings()
    assert len(out["line_colors"]) == 6                       # the loaded copy is padded
    assert len(out["header_map"]) == 6
    assert tag.DEFAULT_SETTINGS["line_colors"] == before      # module default UNCHANGED
    assert len(tag.DEFAULT_SETTINGS["line_colors"]) == 4


def test_save_settings_reports_failure_and_keeps_original(tag, tmp_path, monkeypatch):
    p = tmp_path / "settings.json"
    p.write_text('{"good": true}', encoding="utf-8")
    _point_settings_at(tag, monkeypatch, p)

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(tag.json, "dump", boom)             # fail mid-write
    assert tag.save_settings({"new": 1}) is False           # honest failure, not a false success
    assert p.read_text(encoding="utf-8") == '{"good": true}'  # original intact (atomic temp write)
    assert not (tmp_path / "settings.json.tmp").exists()      # temp cleaned up


def test_corrupt_settings_backed_up_not_silently_lost(tag, tmp_path, monkeypatch):
    p = tmp_path / "settings.json"
    p.write_text("{not valid json", encoding="utf-8")
    _point_settings_at(tag, monkeypatch, p)
    out = tag.load_settings()
    assert out["num_lines"] == 4                              # degraded to defaults
    assert (tmp_path / "settings.json.corrupt").exists()      # bad file preserved, not discarded
    assert not p.exists()                                     # canonical path freed for a clean save


# --------------------------------------------------------------------------
# TAG (fonts) — resolve_font identity naming + fallback signalling
# --------------------------------------------------------------------------
import os
import shutil

_WIN_TTF = r"C:\Windows\Fonts\arial.ttf"


def test_resolve_font_no_path_passes_name_through(tag):
    assert tag.resolve_font("Times-Roman", None) == ("Times-Roman", False)
    assert tag.resolve_font("", None) == ("Helvetica", False)


def test_ensure_font_backward_compatible(tag):
    assert tag.ensure_font("Courier", None) == "Courier"


def test_resolve_font_reports_fallback_on_bad_ttf(tag, tmp_path):
    bad = tmp_path / "notreally.ttf"
    bad.write_bytes(b"this is definitely not a font file")
    name, fallback = tag.resolve_font("", str(bad))
    assert fallback is True
    assert name == "Helvetica"


@pytest.mark.skipif(not os.path.exists(_WIN_TTF), reason="needs a system TTF")
def test_resolve_font_distinct_files_never_collide(tag, tmp_path):
    # Two DIFFERENT files with the same basename ("Arial.ttf") — and both requested under
    # the same "Helvetica" name — must register under DISTINCT names so the second file's
    # glyphs are not silently reused from the first (the in-session cache collision).
    a = tmp_path / "dirA" / "Arial.ttf"
    b = tmp_path / "dirB" / "Arial.ttf"
    a.parent.mkdir()
    b.parent.mkdir()
    shutil.copy(_WIN_TTF, a)
    shutil.copy(_WIN_TTF, b)
    na, fa = tag.resolve_font("Helvetica", str(a))
    nb, fb = tag.resolve_font("Helvetica", str(b))
    assert fa is False and fb is False
    assert na != nb
    assert na != "Helvetica" and nb != "Helvetica"


# --------------------------------------------------------------------------
# TAG (render) — _fit_font_pt shrink-to-width
# --------------------------------------------------------------------------
def test_fit_font_pt_shrinks_overflow_and_leaves_short_text(tag):
    from reportlab.pdfbase import pdfmetrics
    text = "X" * 40
    # 40 chars at 72pt is far wider than a 200pt box -> shrink to fit (well above the 1pt floor).
    fitted = tag._fit_font_pt("Helvetica", text, 72.0, 200.0)
    assert 1.0 < fitted < 72.0
    assert pdfmetrics.stringWidth(text, "Helvetica", fitted) <= 200.0 + 0.5
    # Short text within the box is never grown.
    assert tag._fit_font_pt("Helvetica", "Hi", 12.0, 500.0) == 12.0
    # Degenerate inputs pass through unchanged.
    assert tag._fit_font_pt("Helvetica", "", 12.0, 100.0) == 12.0
    assert tag._fit_font_pt("Helvetica", "Hi", 12.0, 0.0) == 12.0


def test_generate_labels_still_ok_with_overflowing_value(tag, tmp_path):
    csv = tmp_path / "long.csv"
    csv.write_text("Line1,Line2\n" + "M" * 300 + ",short\n", encoding="utf-8")
    out = tmp_path / "long.pdf"
    tag.generate_labels(str(csv), str(out), [72, 72], [0, 0],
                        label_width_in=2, label_height_in=1)
    assert out.exists() and out.stat().st_size > 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
