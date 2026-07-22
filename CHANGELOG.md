# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The application version is single-sourced as `__version__` in
`Automated Tag Creator V5 by LxveAce -Source Code.py`.

## [Unreleased]

## [5.1.0] - 2026-07-22

### Added
- `.gitignore` covering Python caches, virtual environments, and PyInstaller
  build artifacts (`build/`, `dist/`, `*.spec`, `version.txt`).
- Single source of truth for the app name/version via `__version__` and
  `APP_TITLE` constants; the GUI window title and header now reference
  `APP_TITLE`.
- `tests/` pytest suite exercising the pure/core functions (hex-color parsing,
  safe float parsing, robust CSV intake, per-line text mapping) plus the
  `generate_labels` page-count and empty-CSV invariants, with a
  `requirements-dev.txt`.

### Changed
- The per-user settings folder is now named after the app
  (`%APPDATA%\AutomatedTagCreator` on Windows, `~/.automated_tag_creator`
  elsewhere), and the bootstrapper builds under a matching name. If you used an
  earlier build, your last-used settings won't carry over — the app opens with
  its defaults and re-saves on the next generate.

### Fixed
- `parse_hex_color` (and the live-preview color parser) now return the
  documented black fallback for non-hex characters (e.g. `#GGGGGG`) instead of
  raising `ValueError`.
- `generate_labels` now rejects an empty / header-only CSV with a clear error
  instead of silently producing a 0-page, unopenable PDF that the UI reported
  as a success.
- The Bootstrapper build script now points `APP_PY` at the real
  `-Source Code` source filename, so the one-click PyInstaller build can find
  the source.
- `robust_read_csv` now reads every column as text (`dtype=str`), so label
  identifiers such as `007` or `1.50` print verbatim instead of being
  reformatted (to `7` / `1.5`) by pandas type inference; blank cells still
  render as empty lines.
- `robust_read_csv` no longer shreds single-column CSVs. Delimiter detection
  now uses a restricted header-based sniff (comma/semicolon/tab/pipe) that
  falls back to comma, replacing `csv.Sniffer`, which mis-detected a delimiter
  inside single-column files (e.g. splitting `Name` into `['Na', 'e']`).

### Changed
- Simplified the vestigial multi-tile page bookkeeping in `generate_labels` to
  an explicit one-page-per-row `showPage()`. Behavior-preserving: the PDF page
  size already equals the label size, so exactly one label was ever drawn per
  page.

### Removed
- `This is what i do.txt` — an informal setup/usage note fully superseded by the
  overhauled `README.md` (install, CSV format, and the one-click EXE build are
  all documented there).

## [5.0.0] - 2025-12-23

Initial public release of the V5 tag/label PDF generator.

### Added
- CustomTkinter desktop GUI producing measurement-accurate tag/label PDFs from
  CSV input (one label per page).
- Configurable label geometry, built-in and TTF fonts, per-line sizes /
  vertical offsets / hex colors, optional 2- or 4-hole rivet punches, and an
  Inches/Points units toggle.
- Robust CSV intake (delimiter inference + UTF-8 BOM stripping), header-mapping
  UI, JSON template save/load, settings persistence, and a live 150-DPI
  preview.

### Security
- Scrubbed the author's legal name and personal email from the source code,
  in-app branding, and documentation; attributed to the alias **LxveAce**
  (`lxveace@proton.me`).
