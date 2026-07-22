
# Automated Tag Creator V5 by LxveAce
# Requires: customtkinter, pandas, reportlab, pillow
# Install: python -m pip install customtkinter pandas reportlab pillow
import copy
import csv
import hashlib
import os
import json
import platform
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
from typing import List, Optional, Tuple
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageTk
import pandas as pd
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --------------------
# App metadata (single source of truth for name/version)
# --------------------
__version__ = "5.0.0"
APP_TITLE = "Automated Tag Creator V5 by LxveAce"

# --------------------
# Settings persistence
# --------------------
DEFAULT_SETTINGS = {
    "use_inches": True,  # True => inches, False => points (for line sizes & heights)
    # Font / file
    "font_name": "",
    "font_path": None,
    # Label geometry (inches) - true-zero launch
    "label_width_in": 0.0,
    "label_height_in": 0.0,
    # Holes (true-zero launch)
    "holes_enabled": False,
    "holes_count": 2,
    "hole_diameter_in": 0.0,
    "hole_edge_margin_in": 0.0,
    # Colors (hex)
    "outline_color": "#000000",
    "background_color": "#FFFFFF",
    "hole_outline_color": "#000000",
    # Lines
    "num_lines": 4,
    "font_sizes": ["0", "0", "0", "0"],  # interpreted per units toggle
    "heights": ["0", "0", "0", "0"],     # interpreted per units toggle
    # NEW: per-line text colors (hex) - default black for each line
    "line_colors": ["#000000", "#000000", "#000000", "#000000"],
    # Header mapping defaults (per line; "<auto>" means name-first, positional fallback)
    "header_map": ["<auto>", "<auto>", "<auto>", "<auto>"],
    # Preview from CSV toggle (off by default)
    "preview_from_csv": False,
}

def _settings_dir() -> str:
    # Per-user config dir named after the app. (A missing settings.json is treated as a clean first
    # run by load_settings(), so a fresh install just opens with the defaults.)
    if platform.system() == "Windows":
        base = os.getenv("APPDATA", os.path.expanduser("~"))
        folder = os.path.join(base, "AutomatedTagCreator")
    else:
        folder = os.path.join(os.path.expanduser("~"), ".automated_tag_creator")
    os.makedirs(folder, exist_ok=True)
    return folder

def _settings_path() -> str:
    return os.path.join(_settings_dir(), "settings.json")

def _backup_corrupt_settings(path: str, err: Exception) -> None:
    """A settings.json that EXISTS but won't parse (truncated write, bad JSON, a
    hand-edit) must not be silently discarded: move it aside to <path>.corrupt so
    the next save can't overwrite the (possibly recoverable) original and the loss
    is visible instead of silent. An absent file is a clean first run — no backup."""
    try:
        os.replace(path, path + ".corrupt")   # atomic move aside; frees the canonical path
        print(f"Corrupt settings backed up to {path}.corrupt: {err}")
    except Exception:
        pass

def load_settings() -> dict:
    path = _settings_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # deepcopy: DEFAULT_SETTINGS holds mutable lists (header_map, line_colors,
            # font_sizes, heights). A shallow .copy() aliases them, so the pad-loops
            # below would mutate the module-global defaults in place. Deep-copy severs that.
            out = copy.deepcopy(DEFAULT_SETTINGS)
            out.update(data or {})
            out["holes_count"] = 2 if out.get("holes_count") not in [2, 4] else out["holes_count"]
            # ensure header_map length (copy so the pad-loop never writes through a shared ref)
            hm = out.get("header_map")
            hm = list(hm) if isinstance(hm, list) else []
            while len(hm) < int(out.get("num_lines", 4)):
                hm.append("<auto>")
            out["header_map"] = hm
            # NEW: ensure line_colors length
            lc = out.get("line_colors")
            lc = list(lc) if isinstance(lc, list) else []
            while len(lc) < int(out.get("num_lines", 4)):
                lc.append("#000000")
            out["line_colors"] = lc
            return out
        except Exception as e:
            _backup_corrupt_settings(path, e)
    return copy.deepcopy(DEFAULT_SETTINGS)

def save_settings(settings: dict) -> bool:
    """Persist settings atomically. Returns True on success, False on failure so the
    caller can surface a real error instead of a false 'saved' confirmation. Writes a
    sibling temp file then os.replace()s it in, so a crash mid-write can never truncate
    a good settings.json to zero bytes."""
    path = _settings_path()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)   # atomic on the same volume
        return True
    except Exception as e:
        print(f"Could not save settings: {e}")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False

# ----------------------------
# Helpers / safe parsing
# ----------------------------
def parse_hex_color(hex_str: str) -> Tuple[float, float, float]:
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join([ch*2 for ch in s])
    if len(s) != 6:
        return (0.0, 0.0, 0.0)  # fallback black
    try:
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
    except ValueError:
        return (0.0, 0.0, 0.0)  # fallback black on non-hex characters
    return (r, g, b)

def _to_float(val) -> float:
    """Safe float parser; returns 0.0 on failure or blank."""
    try:
        if hasattr(val, "get"):
            val = val.get()
        if val is None:
            return 0.0
        if isinstance(val, str):
            val = val.strip()
            if val == "":
                return 0.0
        return float(val)
    except Exception:
        return 0.0

# ----------------------------
# Font handling (simple/general)
# ----------------------------
def _font_registration_name(font_path: str) -> str:
    """A reportlab registration name that encodes the file's identity (abspath +
    mtime), so two DIFFERENT ttf files never collide under one name — a second
    'Arial.ttf' from another folder used to reuse the first file's glyphs because
    the guard saw the name already registered. A changed file (new mtime) re-registers."""
    base = os.path.splitext(os.path.basename(font_path))[0]
    base = "".join(ch for ch in base if ch.isalnum()) or "CustomFont"
    try:
        stamp = "%d" % int(os.path.getmtime(font_path))
    except Exception:
        stamp = "0"
    h = hashlib.sha1(("%s|%s" % (os.path.abspath(font_path), stamp)).encode("utf-8")).hexdigest()[:8]
    return "%s_%s" % (base, h)

def resolve_font(font_name: str = "Helvetica", font_path: Optional[str] = None) -> Tuple[str, bool]:
    """Resolve the reportlab font to draw with. Returns (registered_name, used_fallback).

    used_fallback is True only when a font_path was supplied but could not be registered
    (corrupt/unsupported/locked ttf) — so the caller can warn instead of silently shipping
    a Helvetica PDF while the UI reports success. When a valid path is given the name
    encodes the file identity so distinct ttf files never collide in one session."""
    if font_path:
        try:
            reg = _font_registration_name(font_path)
            if reg not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(reg, font_path))
            return reg, False
        except Exception:
            return "Helvetica", True
    return (font_name or "Helvetica"), False

def ensure_font(font_name: str = "Helvetica", font_path: Optional[str] = None) -> str:
    return resolve_font(font_name, font_path)[0]

def _fit_font_pt(font_name: str, text: str, size_pt: float, max_width_pt: float) -> float:
    """Shrink size_pt (down only, never up) so `text` fits within max_width_pt at the given
    registered font. Prevents a long CSV value from silently running off the label edge —
    reportlab does not wrap or clip, so an over-wide line otherwise prints past the outline."""
    if not text or size_pt <= 0 or max_width_pt <= 0:
        return size_pt
    try:
        w = pdfmetrics.stringWidth(text, font_name, size_pt)
    except Exception:
        return size_pt
    if w <= max_width_pt:
        return size_pt
    return max(1.0, size_pt * (max_width_pt / w))

# ----------------------------
# CSV intake / map
# ----------------------------
def _sniff_delimiter(path: str) -> str:
    """Pick a delimiter from a restricted candidate set by parsing the header line
    with the csv module (quote-aware) and preferring the delimiter that yields the
    most fields, defaulting to comma. Unlike a raw character count this respects
    quoting, so a comma inside a quoted header (e.g. `"Size, mm";Weight`) no longer
    beats the real semicolon; and it still avoids csv.Sniffer's habit of
    mis-detecting a delimiter in single-column files ('Name' stays one column)."""
    candidates = [",", ";", "\t", "|"]
    header = ""
    for enc in ("utf-8-sig", "cp1252"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                header = f.readline()
            break
        except Exception:
            continue
    best, best_fields = ",", 1
    for d in candidates:
        try:
            n = len(next(csv.reader([header], delimiter=d)))
        except Exception:
            n = 1
        if n > best_fields:      # first candidate to split wins; a later tie can't override
            best, best_fields = d, n
    return best

def _dedupe_columns(cols: List[str]) -> List[str]:
    """Make column labels unique after stripping. A trailing/leading space in one
    header ('Part' vs 'Part ') otherwise strips to two identical 'Part' columns, and
    row.get('Part') then returns a 2-column Series that crashes pick_text_for_line
    with 'truth value of a Series is ambiguous'. Suffix later duplicates .1/.2 like
    pandas' own mangling."""
    seen: dict = {}
    out: List[str] = []
    for c in cols:
        if c in seen:
            seen[c] += 1
            out.append(f"{c}.{seen[c]}")
        else:
            seen[c] = 0
            out.append(c)
    return out

def robust_read_csv(path: str) -> pd.DataFrame:
    # delimiter inference (restricted, single-column-safe) + BOM stripping + header
    # normalization. dtype=str keeps label text verbatim so identifiers like "007"
    # or "1.50" are not reformatted. keep_default_na/na_filter False: never coerce a
    # literal cell ("NA", "NULL", "None", "N/A", ...) to NaN — for a label tool those
    # are valid text, not "missing" (a genuinely empty cell still reads as ""). Excel's
    # legacy "CSV (Comma delimited)" export uses the system ANSI code page, so fall
    # back to cp1252 when utf-8 can't decode (e.g. a degree sign or accented name).
    sep = _sniff_delimiter(path)
    read_kw = dict(sep=sep, engine="python", dtype=str,
                   keep_default_na=False, na_filter=False)
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", **read_kw)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="cp1252", **read_kw)
    df.columns = _dedupe_columns([str(c).strip() for c in df.columns])
    return df

def _cell(val) -> str:
    """Coerce one looked-up cell to display text. Guards against row.get() returning
    a Series (duplicate columns) and treats NaN/None as empty."""
    if isinstance(val, pd.Series):
        val = val.iloc[0] if len(val) else ""
    return "" if pd.isna(val) else str(val)

def pick_text_for_line(df: pd.DataFrame, row: pd.Series, i: int, selected_name: Optional[str]) -> str:
    # Use selected header if provided and present
    if selected_name and selected_name not in ["", "<auto>"] and selected_name in df.columns:
        return _cell(row.get(selected_name))
    # Otherwise name-first candidates + positional fallback
    idx = i + 1
    candidates = [f"Line{idx}", f"Line {idx}", f"line{idx}", f"line_{idx}", f"LINE{idx}", f"LINE {idx}"]
    for name in candidates:
        if name in df.columns:
            return _cell(row.get(name))
    # positional fallback
    return _cell(row.iloc[i]) if i < len(row) else ""

# ----------------------------
# Label generator
# ----------------------------
def generate_labels(
    input_file: str,
    output_file: str,
    font_sizes_pts: List[float],  # points
    heights_pts: List[float],     # points
    font_name: str = "Helvetica",
    font_path: Optional[str] = None,
    holes_enabled: bool = False,
    holes_count: int = 2,
    hole_diameter_in: float = 0.0,
    hole_edge_margin_in: float = 0.0,
    outline_color_hex: str = "#000000",
    background_color_hex: str = "#FFFFFF",
    hole_outline_color_hex: str = "#000000",
    label_width_in: float = 0.0,
    label_height_in: float = 0.0,
    header_map: Optional[List[str]] = None,
    # NEW: per-line text colors
    line_colors_hex: Optional[List[str]] = None,
) -> None:
    # Validate label size
    if label_width_in <= 0 or label_height_in <= 0:
        raise ValueError("Label width/height must be > 0 inches.")
    # Read CSV (robust)
    df = robust_read_csv(input_file)
    # Guard: a header-only / empty CSV would otherwise emit a 0-page, unopenable PDF
    if df is None or len(df) == 0:
        raise ValueError("CSV has no data rows.")
    use_font = ensure_font(font_name, font_path)
    label_width = label_width_in * inch
    label_height = label_height_in * inch
    c = canvas.Canvas(output_file, pagesize=(label_width, label_height))
    outline_rgb = parse_hex_color(outline_color_hex)
    bg_rgb = parse_hex_color(background_color_hex)
    hole_rgb = parse_hex_color(hole_outline_color_hex)
    hole_diameter = hole_diameter_in * inch
    hole_radius = hole_diameter / 2 if hole_diameter > 0 else 0
    hole_edge_margin = hole_edge_margin_in * inch

    def draw_rivet_holes(current_top_y: float):
        if not holes_enabled or hole_radius <= 0:
            return
        c.setStrokeColorRGB(*hole_rgb)
        if holes_count == 2:
            cx_left = hole_edge_margin + hole_radius
            cx_right = label_width - hole_edge_margin - hole_radius
            cy = current_top_y - label_height / 2
            c.circle(cx_left, cy, hole_radius)
            c.circle(cx_right, cy, hole_radius)
        else:
            top_y = current_top_y
            bottom_y = current_top_y - label_height
            cx_left = hole_edge_margin + hole_radius
            cx_right = label_width - hole_edge_margin - hole_radius
            cy_top = top_y - hole_edge_margin - hole_radius
            cy_bottom = bottom_y + hole_edge_margin + hole_radius
            c.circle(cx_left, cy_top, hole_radius)
            c.circle(cx_right, cy_top, hole_radius)
            c.circle(cx_left, cy_bottom, hole_radius)
            c.circle(cx_right, cy_bottom, hole_radius)

    def rgb_for_line(i: int):
        hexv = (line_colors_hex[i] if line_colors_hex and i < len(line_colors_hex) else "#000000")
        return parse_hex_color(hexv)

    for _, row in df.iterrows():
        num_lines = len(font_sizes_pts)
        center_x = label_width / 2
        center_y = label_height / 2
        # Vertical positions (points from center)
        y_positions = []
        for i in range(num_lines):
            offset_pts = heights_pts[i] if i < len(heights_pts) else 0.0
            y_positions.append(center_y + offset_pts)

        # Fill + outline
        c.setFillColorRGB(*bg_rgb)
        c.rect(0, 0, label_width, label_height, fill=1, stroke=0)
        c.setStrokeColorRGB(*outline_rgb)
        c.rect(0, 0, label_width, label_height, fill=0, stroke=1)

        # Holes (optional)
        draw_rivet_holes(label_height)

        # Text
        for i in range(num_lines):
            # Minimal size safety: if size is 0, use 12pt so output isn't blank
            size_pt = float(font_sizes_pts[i]) if i < len(font_sizes_pts) else 0.0
            if size_pt <= 0:
                size_pt = 12.0

            sel_name = header_map[i] if header_map and i < len(header_map) else "<auto>"
            text = pick_text_for_line(df, row, i, sel_name)

            # Fit-to-width: shrink (never grow) so a long value doesn't run past the label edge.
            size_pt = _fit_font_pt(use_font, text, size_pt, label_width * 0.94)
            c.setFont(use_font, size_pt)

            # NEW: set per-line text color
            r, g, b = rgb_for_line(i)
            c.setFillColorRGB(r, g, b)

            c.drawCentredString(center_x, y_positions[i], text)

        # One label per page (page size equals label size)
        c.showPage()

    c.save()

# ----------------------------
# V5 App (CustomTkinter UI)
# ----------------------------
class TagApp(ctk.CTk):
    PREVIEW_DPI = 150

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title(APP_TITLE)
        self.geometry("1220x920")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        s = load_settings()

        # Persistent vars
        self.use_inches = tk.BooleanVar(value=bool(s.get("use_inches", True)))
        self.font_name = tk.StringVar(value=s.get("font_name", ""))
        self.font_path = tk.StringVar(value=s.get("font_path") or "")
        self.label_width_in = tk.StringVar(value=str(s.get("label_width_in", 0.0)))
        self.label_height_in = tk.StringVar(value=str(s.get("label_height_in", 0.0)))
        self.holes_enabled = tk.BooleanVar(value=bool(s.get("holes_enabled", False)))
        self.holes_count = tk.StringVar(value=str(s.get("holes_count", 2)))
        self.hole_diameter_in = tk.StringVar(value=str(s.get("hole_diameter_in", 0.0)))
        self.hole_edge_margin_in = tk.StringVar(value=str(s.get("hole_edge_margin_in", 0.0)))
        self.outline_color = tk.StringVar(value=s.get("outline_color", "#000000"))
        self.background_color = tk.StringVar(value=s.get("background_color", "#FFFFFF"))
        self.hole_outline_color = tk.StringVar(value=s.get("hole_outline_color", "#000000"))
        self.num_lines = tk.StringVar(value=str(s.get("num_lines", 4)))
        self.csv_path = tk.StringVar(value="")
        self.pdf_path = tk.StringVar(value="")
        # Header mapping & preview toggle
        self.header_map_vars: List[tk.StringVar] = []
        self.preview_from_csv = tk.BooleanVar(value=bool(s.get("preview_from_csv", False)))
        # Per-line inputs
        self.font_sizes_vars: List[tk.StringVar] = []
        self.heights_vars: List[tk.StringVar] = []
        # NEW: per-line color vars
        self.line_color_vars: List[tk.StringVar] = []

        # Data cache
        self.df: Optional[pd.DataFrame] = None
        self.column_names: List[str] = []
        # Preview artifacts
        self.preview_ctk_image = None

        # Scrollable main frame
        self.scroll = ctk.CTkScrollableFrame(self, corner_radius=12, fg_color="#332255")
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        for col in range(10):
            self.scroll.grid_columnconfigure(col, weight=1)

        self._build_ui()
        self._refresh_line_fields(preload=s)
        self._refresh_mapping_ui(preload=s)
        self._attach_live_traces()
        self._render_preview()

    def _build_ui(self):
        pad_x, pad_y = 8, 6
        ctk.CTkLabel(self.scroll, text=APP_TITLE,
                     font=("Segoe UI", 20, "bold")).grid(row=0, column=0, columnspan=8, sticky="w", padx=pad_x, pady=pad_y)
        # Units segmented button
        ctk.CTkLabel(self.scroll, text="Units:").grid(row=0, column=6, sticky="e", padx=pad_x, pady=pad_y)
        self.units_segment = ctk.CTkSegmentedButton(self.scroll, values=["Inches", "Points"],
                                                    command=self._on_units_change)
        self.units_segment.grid(row=0, column=7, sticky="w", padx=pad_x, pady=pad_y)
        self.units_segment.set("Inches" if self.use_inches.get() else "Points")

        # Files
        ctk.CTkLabel(self.scroll, text="Input CSV:").grid(row=1, column=0, sticky="e", padx=pad_x, pady=pad_y)
        ctk.CTkEntry(self.scroll, width=600, textvariable=self.csv_path).grid(row=1, column=1, columnspan=5, sticky="ew", padx=pad_x, pady=pad_y)
        ctk.CTkButton(self.scroll, text="Browse...", command=self._browse_csv).grid(row=1, column=6, sticky="w", padx=pad_x, pady=pad_y)

        ctk.CTkLabel(self.scroll, text="Output PDF:").grid(row=2, column=0, sticky="e", padx=pad_x, pady=pad_y)
        ctk.CTkEntry(self.scroll, width=600, textvariable=self.pdf_path).grid(row=2, column=1, columnspan=5, sticky="ew", padx=pad_x, pady=pad_y)
        ctk.CTkButton(self.scroll, text="Browse...", command=self._browse_pdf).grid(row=2, column=6, sticky="w", padx=pad_x, pady=pad_y)

        # Fonts
        ctk.CTkLabel(self.scroll, text="Built-in font (PDF only):").grid(row=3, column=0, sticky="e", padx=pad_x, pady=pad_y)
        ctk.CTkOptionMenu(self.scroll, values=["", "Helvetica", "Times-Roman", "Courier"],
                          variable=self.font_name).grid(row=3, column=1, sticky="w", padx=pad_x, pady=pad_y)
        ctk.CTkLabel(self.scroll, text="TTF path (PDF & preview):").grid(row=3, column=2, sticky="e", padx=pad_x, pady=pad_y)
        ctk.CTkEntry(self.scroll, width=400, textvariable=self.font_path).grid(row=3, column=3, columnspan=2, sticky="ew", padx=pad_x, pady=pad_y)
        ctk.CTkButton(self.scroll, text="Browse TTF...", command=self._browse_ttf).grid(row=3, column=5, sticky="w", padx=pad_x, pady=pad_y)

        # Label geometry
        ctk.CTkLabel(self.scroll, text="Label width (in):").grid(row=4, column=0, sticky="e", padx=pad_x, pady=pad_y)
        ctk.CTkEntry(self.scroll, width=120, textvariable=self.label_width_in).grid(row=4, column=1, sticky="w", padx=pad_x, pady=pad_y)
        ctk.CTkLabel(self.scroll, text="Label height (in):").grid(row=4, column=2, sticky="e", padx=pad_x, pady=pad_y)
        ctk.CTkEntry(self.scroll, width=120, textvariable=self.label_height_in).grid(row=4, column=3, sticky="w", padx=pad_x, pady=pad_y)

        # Holes (collapsible)
        ctk.CTkLabel(self.scroll, text="Rivet holes:").grid(row=5, column=0, sticky="e", padx=pad_x, pady=pad_y)
        self.holes_checkbox = ctk.CTkCheckBox(self.scroll, text="Enable", variable=self.holes_enabled,
                                              command=self._toggle_rivet_section)
        self.holes_checkbox.grid(row=5, column=1, sticky="w", padx=pad_x, pady=pad_y)
        self.rivet_frame = ctk.CTkFrame(self.scroll, corner_radius=12, fg_color="#3a2966")
        self.rivet_frame.grid(row=6, column=0, columnspan=8, sticky="ew", padx=pad_x, pady=pad_y)
        for col in range(8):
            self.rivet_frame.grid_columnconfigure(col, weight=1)
        ctk.CTkLabel(self.rivet_frame, text="Holes (2 or 4):").grid(row=0, column=0, sticky="e", padx=pad_x, pady=pad_y)
        ctk.CTkOptionMenu(self.rivet_frame, values=["2", "4"], variable=self.holes_count,
                          command=lambda _: self._render_preview()).grid(row=0, column=1, sticky="w", padx=pad_x, pady=pad_y)
        ctk.CTkLabel(self.rivet_frame, text="Hole size (in):").grid(row=0, column=2, sticky="e", padx=pad_x, pady=pad_y)
        ctk.CTkEntry(self.rivet_frame, width=120, textvariable=self.hole_diameter_in).grid(row=0, column=3, sticky="w", padx=pad_x, pady=pad_y)
        ctk.CTkLabel(self.rivet_frame, text="Edge margin (in):").grid(row=0, column=4, sticky="e", padx=pad_x, pady=pad_y)
        ctk.CTkEntry(self.rivet_frame, width=120, textvariable=self.hole_edge_margin_in).grid(row=0, column=5, sticky="w", padx=pad_x, pady=pad_y)

        # Colors
        ctk.CTkLabel(self.scroll, text="Outline color (hex):").grid(row=7, column=0, sticky="e", padx=pad_x, pady=pad_y)
        ctk.CTkEntry(self.scroll, width=140, textvariable=self.outline_color).grid(row=7, column=1, sticky="w", padx=pad_x, pady=pad_y)
        ctk.CTkButton(self.scroll, text="Pick…", command=lambda: self._pick_color(self.outline_color)).grid(row=7, column=2, padx=pad_x, pady=pad_y)
        ctk.CTkLabel(self.scroll, text="Background color (hex):").grid(row=7, column=3, sticky="e", padx=pad_x, pady=pad_y)
        ctk.CTkEntry(self.scroll, width=140, textvariable=self.background_color).grid(row=7, column=4, sticky="w", padx=pad_x, pady=pad_y)
        ctk.CTkButton(self.scroll, text="Pick…", command=lambda: self._pick_color(self.background_color)).grid(row=7, column=5, padx=pad_x, pady=pad_y)
        ctk.CTkLabel(self.scroll, text="Hole outline color (hex):").grid(row=7, column=6, sticky="e", padx=pad_x, pady=pad_y)
        ctk.CTkEntry(self.scroll, width=140, textvariable=self.hole_outline_color).grid(row=7, column=7, sticky="w", padx=pad_x, pady=pad_y)

        # Lines count
        ctk.CTkLabel(self.scroll, text="Number of lines:").grid(row=8, column=0, sticky="e", padx=pad_x, pady=pad_y)
        ctk.CTkOptionMenu(self.scroll, values=[str(i) for i in range(1, 11)], variable=self.num_lines,
                          command=lambda _: (self._refresh_line_fields(), self._refresh_mapping_ui(), self._render_preview())).grid(row=8, column=1, sticky="w", padx=pad_x, pady=pad_y)

        # Per-line settings block
        self.lines_frame = ctk.CTkFrame(self.scroll, corner_radius=12, fg_color="#3a2966")
        self.lines_frame.grid(row=9, column=0, columnspan=8, sticky="ew", padx=pad_x, pady=pad_y)
        for col in range(8):
            self.lines_frame.grid_columnconfigure(col, weight=1)

        # Header mapping UI block
        ctk.CTkLabel(self.scroll, text="Header Mapping (choose CSV column for each line)")\
            .grid(row=10, column=0, columnspan=8, sticky="w", padx=pad_x, pady=(pad_y, 0))
        self.mapping_frame = ctk.CTkFrame(self.scroll, corner_radius=12, fg_color="#3a2966")
        self.mapping_frame.grid(row=11, column=0, columnspan=8, sticky="ew", padx=pad_x, pady=pad_y)
        for col in range(8):
            self.mapping_frame.grid_columnconfigure(col, weight=1)

        # Preview controls
        ctk.CTkLabel(self.scroll, text="Live Preview", font=("Segoe UI", 16, "bold"))\
            .grid(row=12, column=0, columnspan=4, sticky="w", padx=pad_x, pady=pad_y)
        self.preview_switch = ctk.CTkSwitch(self.scroll, text="Preview from CSV (first row)", variable=self.preview_from_csv,
                                            command=self._render_preview)
        self.preview_switch.grid(row=12, column=5, sticky="w", padx=pad_x, pady=pad_y)
        self.preview_label = ctk.CTkLabel(self.scroll, text="")
        self.preview_label.grid(row=13, column=0, columnspan=8, sticky="ew", padx=pad_x, pady=pad_y)
        ctk.CTkButton(self.scroll, text="Refresh Preview", command=self._refresh_preview).grid(row=14, column=0, padx=pad_x, pady=pad_y)

        # Actions / Templates
        ctk.CTkButton(self.scroll, text="Generate PDF", command=self._run).grid(row=15, column=0, padx=pad_x, pady=pad_y)
        ctk.CTkButton(self.scroll, text="Save Settings", command=self._save_all_settings).grid(row=15, column=1, padx=pad_x, pady=pad_y)
        ctk.CTkButton(self.scroll, text="Restore Defaults (Zero)", command=self._restore_defaults).grid(row=15, column=2, padx=pad_x, pady=pad_y)
        ctk.CTkButton(self.scroll, text="Save Template", command=self._export_template).grid(row=15, column=3, padx=pad_x, pady=pad_y)
        ctk.CTkButton(self.scroll, text="Load Template", command=self._import_template).grid(row=15, column=4, padx=pad_x, pady=pad_y)

        self._toggle_rivet_section()

    # Units segmented button
    def _on_units_change(self, value: str):
        new_is_inches = (value == "Inches")
        old_is_inches = self.use_inches.get()
        if new_is_inches != old_is_inches:
            factor = 72.0  # 72 pt/in
            # Convert stored values to preserve physical size. Inches->Points multiplies
            # by 72; Points->Inches divides by 72. (Was inverted: a single toggle scaled
            # every font size / height by 72x or 1/72x and silently corrupted the output.)
            for v in self.font_sizes_vars:
                num = _to_float(v)
                v.set(str(num * factor) if old_is_inches else str(num / factor))
            for v in self.heights_vars:
                num = _to_float(v)
                v.set(str(num * factor) if old_is_inches else str(num / factor))
            self.use_inches.set(new_is_inches)
            self._render_preview()

    def _toggle_rivet_section(self):
        if self.holes_enabled.get():
            self.rivet_frame.grid()
        else:
            self.rivet_frame.grid_remove()
        self._render_preview()

    def _refresh_line_fields(self, preload: Optional[dict] = None):
        for child in self.lines_frame.winfo_children():
            child.destroy()
        self.font_sizes_vars = []
        self.heights_vars = []
        self.line_color_vars = []  # NEW reset

        unit = "(in)" if self.use_inches.get() else "(pt)"
        ctk.CTkLabel(self.lines_frame, text=f"Per-line settings (sizes {unit} & vertical offsets {unit})")\
            .grid(row=0, column=0, columnspan=8, padx=8, pady=(6, 10), sticky="w")

        sizes_src = preload.get("font_sizes") if preload else DEFAULT_SETTINGS["font_sizes"]
        heights_src = preload.get("heights") if preload else DEFAULT_SETTINGS["heights"]
        colors_src = preload.get("line_colors") if preload else DEFAULT_SETTINGS["line_colors"]

        for i in range(int(_to_float(self.num_lines)) or 1):
            size_var = tk.StringVar(value=str(sizes_src[i] if i < len(sizes_src) else "0"))
            height_var = tk.StringVar(value=str(heights_src[i] if i < len(heights_src) else "0"))
            color_var = tk.StringVar(value=str(colors_src[i] if i < len(colors_src) else "#000000"))

            self.font_sizes_vars.append(size_var)
            self.heights_vars.append(height_var)
            self.line_color_vars.append(color_var)

            ctk.CTkLabel(self.lines_frame, text=f"Line {i+1} size {unit}").grid(row=1+i, column=0, sticky="e", padx=6, pady=4)
            e1 = ctk.CTkEntry(self.lines_frame, textvariable=size_var, width=120)
            e1.grid(row=1+i, column=1, sticky="w", padx=6, pady=4)
            e1.bind("<KeyRelease>", lambda _e: self._render_preview())

            ctk.CTkLabel(self.lines_frame, text=f"Line {i+1} height {unit}").grid(row=1+i, column=2, sticky="e", padx=6, pady=4)
            e2 = ctk.CTkEntry(self.lines_frame, textvariable=height_var, width=120)
            e2.grid(row=1+i, column=3, sticky="w", padx=6, pady=4)
            e2.bind("<KeyRelease>", lambda _e: self._render_preview())

            # NEW: per-line color controls
            ctk.CTkLabel(self.lines_frame, text=f"Line {i+1} color (hex)").grid(row=1+i, column=4, sticky="e", padx=6, pady=4)
            color_entry = ctk.CTkEntry(self.lines_frame, textvariable=color_var, width=120)
            color_entry.grid(row=1+i, column=5, sticky="w", padx=6, pady=4)
            color_entry.bind("<KeyRelease>", lambda _e: self._render_preview())
            ctk.CTkButton(self.lines_frame, text="Pick…",
                          command=lambda v=color_var: self._pick_color(v)).grid(row=1+i, column=6, padx=6, pady=4)

        self._render_preview()

    def _refresh_mapping_ui(self, preload: Optional[dict] = None):
        # The csv_path write-trace rebuilds this UI on every keystroke; snapshot the
        # user's current per-line selections so a rebuild doesn't wipe them back to
        # '<auto>'. Only a selection whose column no longer exists falls back.
        prior = [v.get() for v in getattr(self, "header_map_vars", [])]
        for child in self.mapping_frame.winfo_children():
            child.destroy()
        self.header_map_vars = []

        # Determine available column names from current CSV
        self.column_names = []
        if self.csv_path.get().strip() and os.path.exists(self.csv_path.get().strip()):
            try:
                self.df = robust_read_csv(self.csv_path.get().strip())
                self.column_names = list(self.df.columns)
            except Exception:
                self.df = None
                self.column_names = []

        # Build drop-downs
        for i in range(int(_to_float(self.num_lines)) or 1):
            ctk.CTkLabel(self.mapping_frame, text=f"Line {i+1} →").grid(row=i, column=0, sticky="e", padx=6, pady=4)
            var = tk.StringVar()
            # preload mapped value if available; else keep the user's prior choice when it
            # still points at an existing column (or '<auto>'); else fall back to '<auto>'.
            if preload and "header_map" in preload and i < len(preload["header_map"]):
                var.set(preload["header_map"][i])
            elif i < len(prior) and (prior[i] == "<auto>" or prior[i] in self.column_names):
                var.set(prior[i])
            else:
                var.set("<auto>")
            self.header_map_vars.append(var)
            options = ["<auto>"] + self.column_names
            ctk.CTkOptionMenu(self.mapping_frame, values=options, variable=var,
                              command=lambda _=None: self._render_preview()).grid(row=i, column=1, sticky="w", padx=6, pady=4)

    def _attach_live_traces(self):
        def on_change(*_):
            self._render_preview()
        # Colors
        self.outline_color.trace_add("write", on_change)
        self.background_color.trace_add("write", on_change)
        self.hole_outline_color.trace_add("write", on_change)
        # Geometry
        self.label_width_in.trace_add("write", on_change)
        self.label_height_in.trace_add("write", on_change)
        # Holes
        self.hole_diameter_in.trace_add("write", on_change)
        self.hole_edge_margin_in.trace_add("write", on_change)
        self.holes_count.trace_add("write", on_change)
        # Font path
        self.font_path.trace_add("write", on_change)
        # Units
        self.use_inches.trace_add("write", on_change)
        # CSV & preview toggle
        self.csv_path.trace_add("write", lambda *_: (self._refresh_mapping_ui(), self._render_preview()))
        self.preview_from_csv.trace_add("write", on_change)

    # File pickers
    def _browse_csv(self):
        path = filedialog.askopenfilename(title="Select input CSV", filetypes=[("CSV files", "*.csv")])
        if path:
            self.csv_path.set(path)
            self._suggest_output_path(path)

    def _browse_pdf(self):
        path = filedialog.asksaveasfilename(title="Save output PDF", defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if path:
            self.pdf_path.set(path)

    def _browse_ttf(self):
        path = filedialog.askopenfilename(title="Select TTF font", filetypes=[("TrueType Font", "*.ttf")])
        if path:
            self.font_path.set(path)

    def _pick_color(self, var: tk.StringVar):
        # The hex field is free text: a partial/garbage value ("12345", "notacolor")
        # passed as -initialcolor raises an unhandled TclError before the dialog opens.
        # Only seed the picker with a valid #hex; otherwise start from black, and guard.
        raw = var.get().strip()
        digits = raw.lstrip("#")
        valid = len(digits) in (3, 6) and all(c in "0123456789abcdefABCDEF" for c in digits)
        initial = ("#" + digits) if valid else "#000000"
        try:
            _, hexval = colorchooser.askcolor(color=initial, title="Pick a color")
        except tk.TclError:
            _, hexval = colorchooser.askcolor(color="#000000", title="Pick a color")
        if hexval:
            var.set(hexval)

    def _suggest_output_path(self, csv_path: str):
        base = os.path.splitext(os.path.basename(csv_path))[0]
        folder = os.path.dirname(csv_path)
        self.pdf_path.set(os.path.join(folder, f"{base}_labels.pdf"))

    # Settings (save/reset)
    def _collect_settings_dict(self) -> dict:
        sizes = [v.get().strip() for v in self.font_sizes_vars]
        heights = [v.get().strip() for v in self.heights_vars]
        header_map = [v.get().strip() for v in self.header_map_vars]
        line_colors = [v.get().strip() or "#000000" for v in self.line_color_vars]  # NEW
        return {
            "use_inches": bool(self.use_inches.get()),
            "font_name": self.font_name.get().strip(),
            "font_path": self.font_path.get().strip() or None,
            "label_width_in": _to_float(self.label_width_in),
            "label_height_in": _to_float(self.label_height_in),
            "holes_enabled": bool(self.holes_enabled.get()),
            "holes_count": int(self.holes_count.get()) if self.holes_count.get() in ["2","4"] else 2,
            "hole_diameter_in": _to_float(self.hole_diameter_in),
            "hole_edge_margin_in": _to_float(self.hole_edge_margin_in),
            "outline_color": self.outline_color.get().strip() or "#000000",
            "background_color": self.background_color.get().strip() or "#FFFFFF",
            "hole_outline_color": self.hole_outline_color.get().strip() or "#000000",
            "num_lines": int(_to_float(self.num_lines) or 4),
            "font_sizes": sizes,
            "heights": heights,
            "line_colors": line_colors,                 # NEW
            "header_map": header_map,
            "preview_from_csv": bool(self.preview_from_csv.get()),
        }

    def _save_all_settings(self):
        s = self._collect_settings_dict()
        if save_settings(s):
            messagebox.showinfo("Saved", "All settings saved.")
        else:
            messagebox.showerror(
                "Save failed",
                f"Could not write settings to:\n{_settings_path()}\n\nYour changes were NOT saved.",
            )

    def _restore_defaults(self):
        s = DEFAULT_SETTINGS.copy()
        self.use_inches.set(bool(s["use_inches"]))
        self.units_segment.set("Inches" if self.use_inches.get() else "Points")
        self.font_name.set(s["font_name"])
        self.font_path.set(s["font_path"] or "")
        self.label_width_in.set(str(s["label_width_in"]))
        self.label_height_in.set(str(s["label_height_in"]))
        self.holes_enabled.set(bool(s["holes_enabled"]))
        self.holes_count.set(str(s["holes_count"]))
        self.hole_diameter_in.set(str(s["hole_diameter_in"]))
        self.hole_edge_margin_in.set(str(s["hole_edge_margin_in"]))
        self.outline_color.set(s["outline_color"])
        self.background_color.set(s["background_color"])
        self.hole_outline_color.set(s["hole_outline_color"])
        self.num_lines.set(str(s["num_lines"]))
        self.preview_from_csv.set(bool(s["preview_from_csv"]))
        self._refresh_line_fields(preload=s)   # includes default per-line colors (#000000)
        self._refresh_mapping_ui(preload=s)
        save_settings(s)
        self._toggle_rivet_section()
        self._render_preview()
        messagebox.showinfo("Restored", "Defaults restored to true zero.")

    # Templates
    def _export_template(self):
        s = self._collect_settings_dict()
        path = filedialog.asksaveasfilename(title="Save Template", defaultextension=".json",
                                            filetypes=[("Template JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(s, f, indent=2)
            messagebox.showinfo("Saved", f"Template saved:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save template:\n{e}")

    def _import_template(self):
        path = filedialog.askopenfilename(title="Load Template", filetypes=[("Template JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            s = DEFAULT_SETTINGS.copy()
            s.update(data or {})
            self.use_inches.set(bool(s["use_inches"]))
            self.units_segment.set("Inches" if self.use_inches.get() else "Points")
            self.font_name.set(s["font_name"])
            self.font_path.set(s["font_path"] or "")
            self.label_width_in.set(str(s["label_width_in"]))
            self.label_height_in.set(str(s["label_height_in"]))
            self.holes_enabled.set(bool(s["holes_enabled"]))
            self.holes_count.set(str(s["holes_count"]))
            self.hole_diameter_in.set(str(s["hole_diameter_in"]))
            self.hole_edge_margin_in.set(str(s["hole_edge_margin_in"]))
            self.outline_color.set(s["outline_color"])
            self.background_color.set(s["background_color"])
            self.hole_outline_color.set(s["hole_outline_color"])
            self.num_lines.set(str(s["num_lines"]))
            self.preview_from_csv.set(bool(s["preview_from_csv"]))
            self._refresh_line_fields(preload=s)  # picks up line_colors from template or defaults
            self._refresh_mapping_ui(preload=s)
            self._toggle_rivet_section()
            self._render_preview()
            messagebox.showinfo("Loaded", f"Template loaded:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not load template:\n{e}")

    # Generate PDF
    def _run(self):
        try:
            csv = self.csv_path.get().strip()
            pdf = self.pdf_path.get().strip()
            if not csv or not os.path.exists(csv):
                raise ValueError("Please choose a valid input CSV.")
            if not pdf:
                raise ValueError("Please choose an output PDF path.")

            use_inches = self.use_inches.get()
            sizes_pts = [(_to_float(v) * 72.0) if use_inches else _to_float(v) for v in self.font_sizes_vars]
            heights_pts= [(_to_float(v) * 72.0) if use_inches else _to_float(v) for v in self.heights_vars]
            font_name = self.font_name.get().strip()
            font_path = self.font_path.get().strip() or None
            holes_enabled = bool(self.holes_enabled.get())
            holes_count = int(self.holes_count.get()) if self.holes_count.get() in ["2","4"] else 2
            hole_diameter_in = _to_float(self.hole_diameter_in)
            hole_edge_margin_in = _to_float(self.hole_edge_margin_in)
            outline_color_hex = self.outline_color.get().strip() or "#000000"
            background_color_hex = self.background_color.get().strip() or "#FFFFFF"
            hole_outline_color_hex= self.hole_outline_color.get().strip() or "#000000"
            label_width_in = _to_float(self.label_width_in)
            label_height_in = _to_float(self.label_height_in)
            header_map = [v.get().strip() for v in self.header_map_vars]
            # NEW: per-line text colors from UI
            line_colors_hex = [v.get().strip() or "#000000" for v in self.line_color_vars]

            self._save_all_settings()
            # Resolve up-front so we can tell the user when a requested TTF could not be
            # loaded — otherwise the whole PDF prints in Helvetica under a "Success" dialog.
            _, font_fallback = resolve_font(font_name or "Helvetica", font_path)
            generate_labels(
                csv, pdf, sizes_pts, heights_pts,
                font_name=font_name or "Helvetica",
                font_path=font_path,
                holes_enabled=holes_enabled,
                holes_count=holes_count,
                hole_diameter_in=hole_diameter_in,
                hole_edge_margin_in=hole_edge_margin_in,
                outline_color_hex=outline_color_hex,
                background_color_hex=background_color_hex,
                hole_outline_color_hex=hole_outline_color_hex,
                label_width_in=label_width_in,
                label_height_in=label_height_in,
                header_map=header_map,
                line_colors_hex=line_colors_hex,  # NEW
            )
            if font_fallback:
                messagebox.showwarning(
                    "Font not loaded",
                    f"The custom TTF could not be loaded:\n{font_path}\n\n"
                    f"The PDF was generated in Helvetica instead:\n{pdf}",
                )
            else:
                messagebox.showinfo("Success", f"PDF generated:\n{pdf}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _refresh_preview(self):
        # The 'Refresh Preview' button must re-read the CSV from disk: _render_preview
        # caches self.df and only reloads it when None or on a path change, so without
        # this an on-disk edit to the same file would never show. Invalidate, then render.
        self.df = None
        self._render_preview()

    # Live preview using CTkImage (no HiDPI warning)
    def _render_preview(self):
        try:
            label_w_in = _to_float(self.label_width_in)
            label_h_in = _to_float(self.label_height_in)
            dpi = self.PREVIEW_DPI
            img_w = max(320, int(max(label_w_in, 1.0) * dpi))
            img_h = max(180, int(max(label_h_in, 1.0) * dpi))
            img = Image.new("RGB", (img_w, img_h), (255, 255, 255))
            draw = ImageDraw.Draw(img)

            def hex_to_rgb255(h):
                h = h.strip().lstrip("#")
                if len(h) == 3:
                    h = "".join(ch*2 for ch in h)
                if len(h) != 6:
                    return (0,0,0)
                try:
                    return (int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))
                except ValueError:
                    return (0,0,0)

            outline_rgb255 = hex_to_rgb255(self.outline_color.get().strip() or "#000000")
            bg_rgb255 = hex_to_rgb255(self.background_color.get().strip() or "#FFFFFF")
            hole_rgb255 = hex_to_rgb255(self.hole_outline_color.get().strip() or "#000000")

            # Fill + outline
            draw.rectangle([(0,0), (img_w-1, img_h-1)], fill=bg_rgb255, outline=None)
            draw.rectangle([(0,0), (img_w-1, img_h-1)], outline=outline_rgb255, width=2)

            # Holes
            holes_enabled = bool(self.holes_enabled.get())
            holes_count = int(self.holes_count.get()) if self.holes_count.get() in ["2","4"] else 2
            hole_diam_in = _to_float(self.hole_diameter_in)
            hole_edge_in = _to_float(self.hole_edge_margin_in)
            hole_radius_px = int((hole_diam_in * dpi) / 2)
            hole_margin_px = int(hole_edge_in * dpi)

            def circle(cx, cy, r, color):
                bbox = [(cx - r, cy - r), (cx + r, cy + r)]
                draw.ellipse(bbox, outline=color, width=2)

            if holes_enabled and hole_radius_px > 0:
                if holes_count == 2:
                    cx_left = hole_margin_px + hole_radius_px
                    cx_right = img_w - hole_margin_px - hole_radius_px
                    cy = img_h // 2
                    circle(cx_left, cy, hole_radius_px, hole_rgb255)
                    circle(cx_right, cy, hole_radius_px, hole_rgb255)
                else:
                    cx_left = hole_margin_px + hole_radius_px
                    cx_right = img_w - hole_margin_px - hole_radius_px
                    cy_top = hole_margin_px + hole_radius_px
                    cy_bottom = img_h - hole_margin_px - hole_radius_px
                    circle(cx_left, cy_top, hole_radius_px, hole_rgb255)
                    circle(cx_right, cy_top, hole_radius_px, hole_rgb255)
                    circle(cx_left, cy_bottom, hole_radius_px, hole_rgb255)
                    circle(cx_right, cy_bottom, hole_radius_px, hole_rgb255)

            # Text lines (preview)
            use_inches = self.use_inches.get()
            sizes_pts = [(_to_float(v) * 72.0) if use_inches else _to_float(v) for v in self.font_sizes_vars]
            heights_pts= [(_to_float(v) * 72.0) if use_inches else _to_float(v) for v in self.heights_vars]

            # Choose text source: CSV or sample
            show_csv = bool(self.preview_from_csv.get())
            texts = []
            if show_csv and self.csv_path.get().strip() and os.path.exists(self.csv_path.get().strip()):
                try:
                    if self.df is None:  # read once
                        self.df = robust_read_csv(self.csv_path.get().strip())
                        self.column_names = list(self.df.columns)
                    # First row text
                    if len(self.df) > 0:
                        row = self.df.iloc[0]
                        header_map = [v.get().strip() for v in self.header_map_vars]
                        for i in range(len(sizes_pts)):
                            sel_name = header_map[i] if i < len(header_map) else "<auto>"
                            texts.append(pick_text_for_line(self.df, row, i, sel_name))
                    else:
                        texts = [f"Line {i+1}" for i in range(len(sizes_pts))]
                except Exception:
                    texts = [f"Line {i+1}" for i in range(len(sizes_pts))]
            else:
                texts = [f"Line {i+1}" for i in range(len(sizes_pts))]

            # Draw text centered horizontally
            center_x_px = img_w // 2
            center_y_px = img_h // 2

            # Font selection for preview: prefer TTF if provided
            font_path = self.font_path.get().strip() or None
            for i, size_pt in enumerate(sizes_pts):
                # Minimal size in preview so you see text
                size_px = max(6, int((size_pt if size_pt > 0 else 12.0) * dpi / 72.0))
                try:
                    if font_path and os.path.exists(font_path):
                        font = ImageFont.truetype(font_path, size=size_px)
                    else:
                        font = ImageFont.load_default()
                except Exception:
                    font = ImageFont.load_default()

                # PIL's origin is top-left (y grows down); the PDF (reportlab) origin is
                # bottom-left (y grows up) and adds the offset. Subtract here so a positive
                # per-line height moves the line the SAME direction in both. (Was inverted.)
                y_px = center_y_px - int((heights_pts[i] if i < len(heights_pts) else 0.0) * dpi / 72.0)

                # Fit-to-width mirror of the PDF path: shrink an overflowing truetype line so
                # a long value doesn't run past the label edge (rough thumbnail for the default font).
                try:
                    max_w = img_w * 0.94
                    text_w = draw.textlength(texts[i], font=font)
                    if text_w > max_w > 0 and font_path and os.path.exists(font_path):
                        font = ImageFont.truetype(font_path, size=max(6, int(size_px * (max_w / text_w))))
                except Exception:
                    pass

                # NEW: per-line color
                hexv = (self.line_color_vars[i].get().strip() if i < len(self.line_color_vars) else "#000000")
                fill_rgb = hex_to_rgb255(hexv)

                draw.text((center_x_px, y_px), texts[i], fill=fill_rgb, font=font, anchor="mm")

            # Tip
            if label_w_in <= 0 or label_h_in <= 0:
                draw.text((10, 10), "Set label width/height (in) > 0 to enable Generate", fill=(255,0,0))

            # CTkImage (no HiDPI warning)
            self.preview_ctk_image = ctk.CTkImage(light_image=img, size=(img_w, img_h))
            self.preview_label.configure(image=self.preview_ctk_image)
        except Exception as e:
            self.preview_label.configure(text=f"Preview error: {e}")

# Entry
if __name__ == "__main__":
    app = TagApp()
    app.mainloop()
