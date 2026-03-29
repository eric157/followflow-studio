# FollowFlow Studio

![FollowFlow mark](assets/followflow-mark.svg)

FollowFlow Studio is a Python desktop toolkit for building a follower cleanup workflow from start to finish:

1. Collect `followers` and `following` from either a logged-in browser session or an Instagram export ZIP.
2. Compare the two lists and generate `non_mutuals.json`.
3. Review profiles one by one in a managed browser session.
4. Keep progress, logs, and resume state between sessions.
5. Update `following.json` after a review session based on the profiles you marked as unfollowed.

The project includes both a CLI and a desktop launcher, so it works well for script users and for people who just want a clickable app.

## Highlights

- Two data-source paths:
  - scrape from a logged-in browser session
  - read from an Instagram export ZIP
- Polished local review control panel with:
  - profile preview
  - progress tracking
  - state badges
  - action buttons
- Resume-safe review sessions with:
  - `review_state.json`
  - `review_log.jsonl`
- Windows-friendly desktop launcher built with Tkinter
- PowerShell build script for a packaged `.exe`

## Project Layout

```text
followflow-studio/
├─ assets/
│  └─ followflow-mark.svg
├─ data/
│  ├─ exports/
│  ├─ processed/
│  │  ├─ followers.json
│  │  ├─ following.json
│  │  └─ non_mutuals.json
│  └─ runtime/
│     ├─ browser-profile/
│     ├─ review_log.jsonl
│     └─ review_state.json
├─ scripts/
│  └─ build_windows_exe.ps1
├─ src/
│  ├─ followflow/
│  │  ├─ browser.py
│  │  ├─ cli.py
│  │  ├─ common.py
│  │  ├─ compare.py
│  │  ├─ export_parser.py
│  │  ├─ launcher.py
│  │  ├─ review.py
│  │  ├─ review_ui.py
│  │  └─ scrape.py
│  └─ instagram_cleanup/
│     └─ ... legacy compatibility shim
├─ followflow_app.py
├─ instagram_export_agent.py
├─ instagram_scrape_agent.py
├─ manual_unfollow_review.py
├─ unfollow_list.py
├─ pyproject.toml
└─ README.md
```

Generated files under `data/`, `build/`, and `dist/` are ignored by Git.

## Requirements

- Python 3.11+
- A Chromium-based browser:
  - Brave
  - Google Chrome
  - Microsoft Edge

## Setup

```bash
python -m pip install -e .
python -m playwright install chromium
```

CLI entry points after install:

```bash
followflow --help
followflow-app
```

If you prefer to run directly from source:

```bash
python -m followflow --help
python followflow_app.py
```

## Desktop Launcher

The fastest way to use the project is the desktop launcher:

```bash
python followflow_app.py
```

What the launcher can do:

- choose `Browser scrape` or `Export ZIP`
- enter the Instagram account username for scrape mode
- browse to an export ZIP for ZIP mode
- run `prepare`
- run `review`
- run the full prepare-to-review flow in one click
- show live logs in a built-in console panel

The launcher starts review sessions without needing terminal input. The local review control panel still opens automatically in your default browser.

If Instagram opens on the login page, sign in directly in the managed browser window. FollowFlow waits there until the session is authenticated, then resumes automatically. If Instagram asks for a code, challenge, `Save login info`, or notification prompt, finish those in the browser and let FollowFlow continue from the same run.

The scrape flow now starts from Instagram's login route so the browser is always in the right place to finish sign-in first. If a logged-out profile or follower-list click later throws a `Log in / Sign up` prompt, FollowFlow returns to the login flow, waits for you to finish it in the browser, then retries the same scrape step automatically.

During the login handoff, FollowFlow also tries to clear the common Instagram blockers automatically, including:

- cookie consent banners
- `Save login info` style prompts
- `Turn on notifications` prompts
- closeable follow-up dialogs that appear immediately after sign-in
- logged-out `Log in / Sign up` prompts that appear when a profile or follower list asks for authentication before opening

## End-to-End Workflow

### Option A: Prepare from a logged-in browser scrape

```bash
followflow prepare --source scrape --username your_instagram_username
```

What happens:

- a managed browser opens with the persistent profile in `data/runtime/browser-profile`
- if needed, FollowFlow waits while you sign into Instagram in that browser
- FollowFlow scrapes your `followers` and `following` lists
- the app writes:
  - `data/processed/followers.json`
  - `data/processed/following.json`
  - `data/processed/non_mutuals.json`

If `--username` is omitted, the tool tries to detect the logged-in username from `https://www.instagram.com/accounts/edit/`.

### Option B: Prepare from your Instagram export ZIP

Request the Instagram export, download the archive, then run:

```bash
followflow prepare --source zip --zip "/full/path/to/instagram-yourusername-YYYY-MM-DD.zip"
```

The toolkit expects the standard export files inside the archive:

- `connections/followers_and_following/followers_1.json`
- `connections/followers_and_following/following.json`

If you omit `--zip`, FollowFlow searches `~/Downloads` for the newest `instagram-*.zip`.

### Generate the non-mutual list only

```bash
followflow compare
```

### Start the review flow

```bash
followflow review
```

What happens:

- a managed browser opens using `data/runtime/browser-profile`
- a local control panel opens on `http://127.0.0.1:<port>`
- one profile at a time is loaded from `data/processed/non_mutuals.json`
- progress is saved as the session advances
- when the profile state changes, the review session reacts and updates the panel

## Review Controls

Terminal commands:

- `u` = mark the current profile as unfollowed
- `f` = toggle the current profile follow state
- `s` = skip the current profile
- `r` = reload the current profile
- `q` = quit and save progress

The local control panel provides matching buttons:

- `Mark Unfollowed`
- `Toggle Follow`
- `Skip`
- `Reload`
- `Quit Session`

Useful review options:

```bash
followflow review --reset
followflow review --no-ui
followflow review --no-terminal
```

- `--reset` starts again from index `0`
- `--no-ui` disables the local control panel
- `--no-terminal` disables terminal commands and uses the control panel only

## Session Files

Runtime files:

- `data/runtime/browser-profile/`
- `data/runtime/review_state.json`
- `data/runtime/review_log.jsonl`

Processed files:

- `data/processed/followers.json`
- `data/processed/following.json`
- `data/processed/non_mutuals.json`

On the first rewrite of `following.json`, a backup is created:

- `data/processed/following.json.bak`

## CLI Reference

### `followflow extract`

Extract clean followers and following lists from an Instagram export ZIP.

```bash
followflow extract --zip "/full/path/to/export.zip"
```

Options:

- `--zip` path to a specific export ZIP
- `--search-root` search location when `--zip` is omitted
- `--output-dir` destination for `followers.json` and `following.json`

### `followflow scrape`

Scrape followers and following lists from a logged-in browser session.

```bash
followflow scrape --username your_instagram_username
```

Options:

- `--username` explicit Instagram username
- `--output-dir` destination for `followers.json` and `following.json`
- `--profile-dir` persistent browser profile
- `--browser` explicit Chromium executable path

### `followflow compare`

Generate `non_mutuals.json` from existing followers and following data.

```bash
followflow compare
```

Options:

- `--followers` path to followers data
- `--following` path to following data
- `--output` destination for `non_mutuals.json`

### `followflow prepare`

Run either ZIP extraction or browser scraping, then compare.

```bash
followflow prepare --source zip --zip "/full/path/to/export.zip"
followflow prepare --source scrape --username your_instagram_username
```

### `followflow review`

Run the managed review workflow.

```bash
followflow review
```

Options:

- `--input` path to `non_mutuals.json` or a text file of usernames and profile URLs
- `--following-file` path to the `following.json` file that should be updated after the session
- `--state` path to the resume state file
- `--log` path to the JSONL review log
- `--profile-dir` path to the persistent browser profile
- `--browser` explicit Chromium executable path
- `--start-at` zero-based override to begin from a specific row
- `--reset` ignore the saved review state and start from `0`
- `--no-ui` disable the local review control panel
- `--no-terminal` disable terminal commands

## Legacy Wrapper Scripts

These compatibility wrappers still work:

```bash
python instagram_export_agent.py --zip "/full/path/to/export.zip"
python instagram_scrape_agent.py --username your_instagram_username
python unfollow_list.py
python manual_unfollow_review.py
```

They map to:

- `instagram_export_agent.py` -> `followflow extract`
- `instagram_scrape_agent.py` -> `followflow scrape`
- `unfollow_list.py` -> `followflow compare`
- `manual_unfollow_review.py` -> `followflow review`

## Build a Windows `.exe`

Use the included PowerShell build script:

```powershell
.\scripts\build_windows_exe.ps1
```

That script:

1. installs the project with the optional build dependencies
2. installs the Playwright Chromium runtime
3. builds a packaged Windows app with PyInstaller

Build output:

```text
dist/FollowFlow/FollowFlow.exe
```

Launch the built app by double-clicking `FollowFlow.exe`.

## Notes

- The browser-state detector assumes English Instagram labels such as `Following`, `Requested`, `Follow`, and `Follow back`.
- If Instagram requires two-factor authentication or another challenge step, complete it in the browser window and the session will continue once the login form disappears.
- If Instagram reports rate limiting such as `Try again later`, the review flow stops and keeps your progress.
- If you want a fresh managed browser session, remove `data/runtime/browser-profile/`.

## Local Tests

Prompt-handling regression tests live in `tests/test_browser_dialogs.py`.

Run them with:

```bash
python -m unittest tests.test_browser_dialogs -v
```
