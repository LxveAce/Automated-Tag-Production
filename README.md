# Automated Tag Creator V5

A Windows desktop GUI for generating measurement-accurate tag/label PDFs from CSV input files. Built with Python, CustomTkinter, ReportLab, pandas, and Pillow.

---

## What it does

Each row in your CSV becomes one label/tag page in the output PDF. You configure every visual aspect of the label — size, fonts, per-line text size and vertical position, colors, and optional rivet holes — then generate the entire batch in one click.

---

## Key features

- **Configurable label size** — enter width and height in inches; the PDF page is set exactly to those dimensions for print-ready output
- **Units toggle** — switch between Inches and Points at any time; per-line values convert automatically
- **Built-in PDF fonts** — Helvetica, Times-Roman, Courier (no extra files needed)
- **TTF font support** — browse to any `.ttf` file; used in both the live preview and the PDF output
- **Per-line control** — up to 10 text lines, each with its own font size, vertical offset, and hex color; color picker included
- **Rivet holes** — optional 2-hole or 4-hole punches with configurable diameter and edge margin, drawn as outlines on the PDF
- **Label outline and background color** — pick hex colors for the label border, fill, and hole outlines
- **CSV header mapping** — map any CSV column to any label line via dropdown; falls back to `Line1`/`Line 1`/positional if left on `<auto>`
- **Robust CSV parsing** — auto-detects delimiter (comma, semicolon, tab), strips UTF-8 BOM, normalizes headers
- **Live preview** — 150 DPI canvas preview updates as you type; toggle "Preview from CSV" to render actual first-row data
- **JSON templates** — save and load the full settings set (geometry, fonts, colors, mapping) as a `.json` file for reuse across jobs
- **Settings persistence** — last-used settings are saved to `%APPDATA%\MMRTagTool\settings.json` automatically on generate
- **One-file EXE build** — ships as pure Python source; package into a standalone Windows executable with PyInstaller

---

## Requirements

- Python 3.11 or 3.12 (use the [python.org](https://python.org) installer, not the Windows Store version)
- Windows (tested on Windows 10/11)

---

## Install and run from source

```powershell
# 1. Open PowerShell in the project folder

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# 3. Install dependencies
python -m pip install --upgrade pip
python -m pip install customtkinter pandas reportlab pillow pyinstaller

# 4. Run
python "Automated Tag Creator V5 by LxveAce -Source Code.py"
```

---

## Quick-start workflow

1. Set **Label width (in)** and **Label height (in)** to non-zero values (e.g., `6` and `3`).
2. Browse to your **Input CSV** and choose an **Output PDF** path.
3. Configure per-line font sizes, vertical heights, and colors as needed.
4. Optionally enable **Rivet holes** and set hole size and edge margin.
5. Use **Header Mapping** to assign CSV columns to label lines, or leave on `<auto>`.
6. Toggle **Preview from CSV** to verify the first row renders correctly.
7. Click **Generate PDF**.

---

## CSV format

The app accepts any delimiter (comma, semicolon, tab) with or without a UTF-8 BOM. Column-to-line mapping options:

| Priority | How the column is selected |
|----------|---------------------------|
| 1 | Header Mapping dropdown — pick the exact column name |
| 2 | Column named `Line1`, `Line 1`, `line1`, `line_1`, `LINE1`, or `LINE 1` |
| 3 | Positional fallback — column at index *i* for line *i* |

---

## Build a standalone EXE

```powershell
# Inside the activated venv:
pyinstaller --noconfirm --onefile --windowed `
    --name "Automated Tag Creator V5 by LxveAce" `
    "Automated Tag Creator V5 by LxveAce -Source Code.py"
```

The executable appears in the `dist\` folder. Optional flags:

- `--icon path\to\icon.ico` — embed a custom icon
- `--clean` — clear PyInstaller cache before building

> PyInstaller builds for the OS it runs on. Build the Windows EXE on Windows.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Blank PDF | Label width/height must be > 0. Lines with size 0 fall back to 12 pt, so output is visible but may not match your layout — set explicit sizes. |
| CSV not read | Verify the file path. The parser auto-detects delimiter and strips BOM. Use Header Mapping if your column names do not follow the `Line1` convention. |
| Wrong interpreter in VS Code | `Ctrl+Shift+P` → **Python: Select Interpreter** → pick the `.venv` entry, then reload the window. |
| PyInstaller not found | Run `python -m pip install pyinstaller` from within the activated venv. |

---

## License

MIT — see [LICENSE](LICENSE).

---

## Disclaimer

Provided **as-is** under the MIT license, with no warranty. Always verify generated tags/labels against your stock, printer, and scanner before any production use.
