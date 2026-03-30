# FollowFlow Studio

> Personal tool for batch-reviewing Instagram followers/following and managing bulk unfollows.

[![GitHub Release](https://img.shields.io/github/v/release/eric157/followflow-studio?label=release)](https://github.com/eric157/followflow-studio/releases/latest)
[![Docker Image](https://img.shields.io/badge/ghcr.io-followflow--studio-blue?logo=docker)](https://ghcr.io/eric157/followflow-studio)
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue?logo=python)](https://www.python.org/)

---

## 📦 Download (Windows)

Grab the latest no-install Windows build from the [**Releases page**](https://github.com/eric157/followflow-studio/releases/latest):

1. Download `FollowFlow-Windows-vX.Y.Z.zip`
2. Extract anywhere
3. Run `FollowFlow.exe`

---

## 🐳 Docker

```bash
# Pull and run (CLI help)
docker pull ghcr.io/eric157/followflow-studio:latest
docker run --rm ghcr.io/eric157/followflow-studio:latest followflow --help

# Full review session (Review UI at http://localhost:5000)
docker compose up
```

See [README_DOCKER.md](README_DOCKER.md) for the full Docker guide.

---

## 🚀 Quick Start (from source)

```bash
pip install -e .
playwright install chromium
followflow --help
```

Or launch the desktop GUI:

```bash
python followflow_app.py
```

---

## Project Layout

```
src/followflow/
├─ launcher.py       # Desktop app (CustomTkinter)
├─ cli.py            # Command-line interface
├─ browser.py        # Playwright browser management
├─ scrape.py         # Instagram scraping logic
├─ export_parser.py  # Parse Instagram export ZIP
├─ compare.py        # Generate non-mutuals list
├─ review.py         # Review workflow
└─ review_ui.py      # Local HTTP review panel
```

---

## Data Directories

```
data/processed/     # followers.json, following.json, non_mutuals.json (git-ignored)
data/runtime/       # browser-profile/, review_state.json, review_log.jsonl (git-ignored)
data/exports/       # Instagram export ZIPs
```

---

## Key Commands

```bash
# Extract from Instagram export ZIP
followflow prepare --source zip --zip "/path/to/export.zip"

# Scrape from logged-in browser session
followflow prepare --source scrape --username <username>

# Generate non-mutuals list
followflow compare

# Start interactive review session
followflow review
```

---

## Notes

- Login session stored in `data/runtime/browser-profile/` (persists between runs)
- Browser profile and processed data are git-ignored for security
- Review state is saved automatically so sessions can be resumed
- Build Windows EXE locally: `.\scripts\build_windows_exe.ps1`
