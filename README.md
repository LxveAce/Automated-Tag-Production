<div align="center">

# Automated Tag Creator V5

### Turn a CSV into print-ready tag and label PDFs — one row, one label, one click.

Exact-inch label sizing · per-line fonts, sizes and colors · optional rivet holes · live preview.

[![License: MIT](https://img.shields.io/github/license/LxveAce/Automated-Tag-Production)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

[Features](#features) · [Install](#install-and-run-from-source) · [CSV format](#csv-format) · [Build an EXE](#build-a-standalone-exe) · [Changelog](CHANGELOG.md)

</div>

---

I built this to stop hand-placing text in a design tool every time a batch of equipment tags came through. Point it at a CSV, set the label size in real inches, and it writes one label per page at exactly those dimensions — so what comes off the printer matches your stock. Each row in the CSV becomes one label: you control the size, fonts, per-line text placement and color, and optional rivet holes, then generate the whole batch at once.

It's a Windows desktop app with a CustomTkinter GUI, built on ReportLab (PDF), pandas (CSV intake), and Pillow (preview). Part of the [ExpertTags](https://experttags.com) label toolset.

---

## Features

- **Exact label size** — enter width and height in inches; the PDF page is set to those dimensions, so a label prints at the size you asked for.
- **Inches / Points toggle** — switch units at any time; per-line values convert automatically.
- **Built-in PDF fonts** — Helvetica, Times-Roman, Courier, no extra files needed.
- **TTF fonts** — browse to any `.ttf`; it's used in both the live preview and the PDF.
- **Per-line control** — up to 10 lines, each with its own font size, vertical offset, and hex color (color picker included).
- **Rivet holes** — optional 2-hole or 4-hole punches with a set diameter and edge margin, drawn as outlines on the PDF.
- **Label border and fill** — pick hex colors for the outline, background, and hole outlines.
- **CSV header mapping** — map any column to any label line from a dropdown; leave it on `<auto>` to fall back to `Line1`/`Line 1`/positional.
- **CSV parsing that doesn't mangle your data** — auto-detects the delimiter (comma, semicolon, tab, or pipe), strips a UTF-8 BOM, and reads every cell as text so identifiers like `007` or `1.50` print verbatim instead of becoming `7` or `1.5`.
- **Live preview** — a 150 DPI canvas updates as you type; flip on "Preview from CSV" to render the actual first row.
- **JSON templates** — save and load the full settings set (geometry, fonts, colors, mapping) for reuse across jobs.
- **Settings persistence** — the last-used settings save to `%APPDATA%\AutomatedTagCreator\settings.json` on generate.
- **One-click EXE build** — ships as plain Python source; the included bootstrapper packages it into a standalone Windows executable with PyInstaller.

---

## Requirements

- Python 3.11 or 3.12 — use the [python.org](https://python.org) installer, not the Windows Store build.
- Windows (built and tested on Windows 10/11).

---

## Install and run from source

```powershell
# 1. Open PowerShell in the project folder

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# 3. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 4. Run
python "Automated Tag Creator V5 by LxveAce -Source Code.py"
```

---

## Quick-start workflow

1. Set **Label width (in)** and **Label height (in)** to non-zero values (e.g. `6` and `3`).
2. Browse to your **Input CSV** and pick an **Output PDF** path.
3. Set per-line font sizes, vertical heights, and colors as needed.
4. Optionally enable **Rivet holes** and set the hole size and edge margin.
5. Use **Header Mapping** to assign CSV columns to lines, or leave it on `<auto>`.
6. Flip on **Preview from CSV** to check that the first row renders the way you want.
7. Click **Generate PDF**.

---

## CSV format

Any delimiter (comma, semicolon, tab, or pipe) works, with or without a UTF-8 BOM. Each line on the label picks its text in this order:

| Priority | How the column is chosen |
|----------|--------------------------|
| 1 | Header Mapping dropdown — the exact column name you picked |
| 2 | A column named `Line1`, `Line 1`, `line1`, `line_1`, `LINE1`, or `LINE 1` |
| 3 | Positional fallback — the column at index *i* for line *i* |

A header-only or empty CSV is rejected with a clear error instead of producing an unopenable, 0-page PDF.

---

## Build a standalone EXE

**One-click:** run `Bootstrapper 1.1.1.bat`. It creates the venv, installs the requirements, and builds a one-file windowed EXE to a local (non-OneDrive) build folder, reporting the output path when it finishes.

**Manual**, inside an activated venv:

```powershell
pyinstaller --noconfirm --onefile --windowed `
    --name "Automated Tag Creator V5 by LxveAce" `
    "Automated Tag Creator V5 by LxveAce -Source Code.py"
```

The executable lands in `dist\`. Useful flags: `--icon path\to\icon.ico` to embed an icon, `--clean` to clear the PyInstaller cache first.

> PyInstaller builds for the OS it runs on. Build the Windows EXE on Windows.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Blank PDF | Label width/height must be > 0. Any line left at size 0 falls back to 12 pt, so text still shows but may not match your layout — set explicit sizes. |
| CSV not read | Check the file path. The parser auto-detects the delimiter and strips a BOM; use Header Mapping if your columns aren't named `Line1`, `Line2`, … |
| Wrong interpreter in VS Code | `Ctrl+Shift+P` → **Python: Select Interpreter** → pick the `.venv` entry, then reload the window. |
| PyInstaller not found | Run `python -m pip install pyinstaller` inside the activated venv. |

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md). The version is single-sourced as `__version__` in the source file.

---

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

Provided **as-is** under the MIT license, with no warranty. Always check generated tags against your stock, printer, and scanner before any production run.

---

## 📫 Connect

**Discord:** [discord.gg/lxvelabs](https://discord.gg/lxvelabs) · **GitHub:** [@LxveAce](https://github.com/LxveAce) · **Email:** LxveLabs@proton.me (business) · lxveace@proton.me (direct) · **Site:** [experttags.com](https://experttags.com)

Built by LxveAce · part of the ExpertTags label toolset
