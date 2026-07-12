"""Constructed-widget regressions for the GUI-coupled audit fixes.

The customtkinter TagApp constructs headlessly in this environment, so these build a
real (withdrawn) window and drive the actual methods:

  * _on_units_change: an Inches<->Points toggle must convert values to PRESERVE physical
    size (was inverted -> a single toggle scaled every size/height by 72x or 1/72x);
  * _pick_color: a partial/garbage hex in the free-text field must not crash the picker;
  * _refresh_preview: the button must invalidate the cached DataFrame so an on-disk edit
    is re-read;
  * _refresh_mapping_ui: rebuilding the mapping UI (fires on every csv_path keystroke) must
    preserve the user's per-line column selections instead of resetting them to '<auto>';
  * _run: a custom TTF that can't be loaded must warn (not report plain "Success").

The preview vertical-offset sign flip (#8, _render_preview) is a one-character PIL(y-down)
-vs-reportlab(y-up) parity fix verified by inspection, mirroring the HMG/UF Tk-parity fixes.

Tk really wants a single root per process, so ONE TagApp is built for the whole module and
reused; each test sets the state it reads.
"""
import importlib.util
import os
import tempfile

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "Automated Tag Creator V5 by LxveAce -Source Code.py")


def _load():
    spec = importlib.util.spec_from_file_location("tag_gui_under_test", _SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def app():
    tag = _load()
    mp = pytest.MonkeyPatch()
    tmpdir = tempfile.mkdtemp()
    mp.setattr(tag, "_settings_path", lambda: os.path.join(tmpdir, "settings.json"))
    try:
        w = tag.TagApp()
    except Exception as e:                      # pragma: no cover - environment guard
        mp.undo()
        pytest.skip(f"TagApp did not construct headlessly: {e}")
    w.withdraw()
    w._tag = tag
    yield w
    try:
        w.destroy()
    except Exception:
        pass
    mp.undo()


def test_units_toggle_preserves_physical_size(app):
    app.use_inches.set(True)
    app.units_segment.set("Inches")
    app.font_sizes_vars[0].set("0.5")           # 0.5 in
    app.heights_vars[0].set("0.25")
    app._on_units_change("Points")              # -> multiply by 72
    assert abs(float(app.font_sizes_vars[0].get()) - 36.0) < 1e-6
    assert abs(float(app.heights_vars[0].get()) - 18.0) < 1e-6
    app._on_units_change("Inches")              # -> divide by 72, round-trips
    assert abs(float(app.font_sizes_vars[0].get()) - 0.5) < 1e-6
    assert abs(float(app.heights_vars[0].get()) - 0.25) < 1e-6


def test_pick_color_normalizes_invalid_hex_and_never_crashes(app):
    tag = app._tag
    captured = {}

    def fake_askcolor(color=None, title=None):
        captured["color"] = color
        return (None, None)                     # user cancels

    _patch_askcolor(tag, fake_askcolor)
    app.outline_color.set("12345")              # garbage: would raise TclError as -initialcolor
    app._pick_color(app.outline_color)          # must not raise
    assert captured["color"] == "#000000"       # normalized, not the garbage
    app.outline_color.set("#aabbcc")
    app._pick_color(app.outline_color)
    assert captured["color"] == "#aabbcc"       # a valid hex is passed through


def test_pick_color_catches_tclerror_from_bad_initial(app):
    tag = app._tag
    calls = {"n": 0}

    def raising_then_ok(color=None, title=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise tag.tk.TclError("unknown color name")
        return (None, None)

    _patch_askcolor(tag, raising_then_ok)
    app.outline_color.set("#aabbcc")
    app._pick_color(app.outline_color)          # the except must retry with black, not crash
    assert calls["n"] == 2


def test_refresh_preview_invalidates_cached_dataframe(app):
    app.df = "STALE-SENTINEL"
    app.csv_path.set("")                         # empty -> render won't reload, leaving df cleared
    app._refresh_preview()
    assert app.df != "STALE-SENTINEL"            # the cache was invalidated (re-read on next render)


def test_mapping_ui_preserves_user_selection_across_rebuild(app, tmp_path):
    p = tmp_path / "map.csv"
    p.write_text("Part,Qty\nA,1\n", encoding="utf-8")
    app.num_lines.set("2")
    app.csv_path.set(str(p))                     # trace rebuilds the mapping UI from the columns
    app._refresh_mapping_ui()
    app.header_map_vars[0].set("Part")           # user picks a real column for line 1
    app._refresh_mapping_ui()                    # a rebuild (e.g. another keystroke) must keep it
    assert app.header_map_vars[0].get() == "Part"


def test_run_warns_when_custom_ttf_cannot_load(app, tmp_path):
    tag = app._tag
    csv = tmp_path / "in.csv"
    csv.write_text("Line1,Line2\nA,B\n", encoding="utf-8")
    pdf = tmp_path / "out.pdf"
    bad = tmp_path / "bad.ttf"
    bad.write_bytes(b"not a font")

    seen = {"warn": [], "info": [], "error": None}
    _patch_messagebox(tag, seen)

    app.label_width_in.set("6")
    app.label_height_in.set("3")
    app.csv_path.set(str(csv))
    app.pdf_path.set(str(pdf))
    app.font_path.set(str(bad))
    app._run()

    assert seen["error"] is None, f"_run errored: {seen['error']}"
    # The font-fallback warning fired; the plain "Success" dialog did NOT (the "Saved"
    # info from _save_all_settings is expected and unrelated).
    assert len(seen["warn"]) == 1
    assert "Success" not in seen["info"]
    assert pdf.exists()                          # the PDF was still produced (in Helvetica)


# --- helpers ---------------------------------------------------------------
def _patch_askcolor(tag, fn):
    import tkinter.colorchooser as cc
    cc.askcolor = fn
    tag.colorchooser.askcolor = fn


def _patch_messagebox(tag, seen):
    tag.messagebox.showwarning = lambda *a, **k: seen["warn"].append(a[0] if a else "")
    tag.messagebox.showinfo = lambda *a, **k: seen["info"].append(a[0] if a else "")
    tag.messagebox.showerror = lambda *a, **k: seen.__setitem__("error", a[1] if len(a) > 1 else a)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
