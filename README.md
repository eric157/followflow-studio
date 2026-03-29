# FollowFlow Studio

Personal project for batch-reviewing Instagram followers/following and managing bulk unfollows.

## Quick Start

```bash
python -m pip install -e .
python -m playwright install chromium
python followflow_app.py
```

Or use the CLI directly:

```bash
followflow --help
```

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

## Data Directories

```
data/processed/     # followers.json, following.json, non_mutuals.json (git-ignored)
data/runtime/       # browser-profile/, review_state.json, review_log.jsonl (git-ignored)
data/exports/       # Instagram export ZIPs
```

## Key Commands

```bash
# Scrape from logged-in browser
followflow prepare --source scrape --username <username>

# Extract from export ZIP
followflow prepare --source zip --zip "/path/to/export.zip"

# Generate non-mutuals list
followflow compare

# Start review session
followflow review
```

## Notes

- Login session stored in `data/runtime/browser-profile/` (keeps you logged in between runs)
- Browser profile and processed data are git-ignored for security
- Review state is saved automatically to resume sessions
- Build exe: `.\scripts\build_windows_exe.ps1`
