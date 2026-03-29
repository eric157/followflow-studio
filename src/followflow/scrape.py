from __future__ import annotations

import re
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from followflow.browser import (
    dialog_requests_authentication,
    dismiss_instagram_dialogs,
    ensure_logged_in_from_current_page,
    launch_persistent_chromium,
    resolve_browser_executable,
    wait_for_login,
)
from followflow.common import (
    DEFAULT_BROWSER_PROFILE_DIR,
    DEFAULT_FOLLOWERS_PATH,
    DEFAULT_FOLLOWING_PATH,
    INSTAGRAM_BASE,
    write_json,
)


COUNT_PATTERN = re.compile(r"(\d[\d,]*)")
RESERVED_PATHS = {
    "accounts",
    "about",
    "api",
    "developer",
    "direct",
    "explore",
    "graphql",
    "legal",
    "p",
    "reel",
    "reels",
    "stories",
}


def current_visible_dialog(page):
    return page.locator("div[role='dialog']:visible").last


def find_list_trigger(page, username: str, list_name: str):
    candidate_selectors = [
        f"a[href='/{username}/{list_name}/']",
        f"a[href$='/{username}/{list_name}/']",
        f"a[href$='/{list_name}/']",
    ]

    for selector in candidate_selectors:
        locator = page.locator(selector).first
        if locator.count():
            return locator
    return None


def parse_count(text: str) -> int | None:
    match = COUNT_PATTERN.search(text.replace(".", ""))
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def resolve_account_username(
    page,
    explicit_username: str | None,
    *,
    login_username: str | None,
    login_password: str | None,
    allow_terminal_input: bool,
) -> str:
    if explicit_username:
        return explicit_username.strip().lstrip("@")

    edit_url = f"{INSTAGRAM_BASE}accounts/edit/"
    page.goto(edit_url, wait_until="domcontentloaded", timeout=60000)
    time.sleep(2)
    dismiss_instagram_dialogs(page, timeout_seconds=6.0)
    ensure_logged_in_from_current_page(
        page,
        login_username=login_username,
        login_password=login_password,
        allow_terminal_input=allow_terminal_input,
        resume_url=edit_url,
    )
    dismiss_instagram_dialogs(page, timeout_seconds=6.0)

    username_input = page.locator("input[name='username']").first
    if username_input.count():
        value = username_input.input_value().strip()
        if value:
            return value

    raise SystemExit(
        "Could not determine the Instagram username from the logged-in session. "
        "Pass --username explicitly."
    )


def ensure_profile_access(
    page,
    profile_url: str,
    *,
    login_username: str | None,
    login_password: str | None,
    allow_terminal_input: bool,
) -> None:
    page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
    time.sleep(2)
    dismiss_instagram_dialogs(page, timeout_seconds=6.0)
    if ensure_logged_in_from_current_page(
        page,
        login_username=login_username,
        login_password=login_password,
        allow_terminal_input=allow_terminal_input,
        resume_url=profile_url,
    ):
        time.sleep(1)
        dismiss_instagram_dialogs(page, timeout_seconds=6.0)


def open_list_dialog(
    page,
    username: str,
    list_name: str,
    *,
    login_username: str | None,
    login_password: str | None,
    allow_terminal_input: bool,
):
    profile_url = f"{INSTAGRAM_BASE}{username}/"
    ensure_profile_access(
        page,
        profile_url,
        login_username=login_username,
        login_password=login_password,
        allow_terminal_input=allow_terminal_input,
    )

    trigger = find_list_trigger(page, username, list_name)
    if trigger is None:
        raise SystemExit(
            f"Could not find the {list_name} link on https://www.instagram.com/{username}/ ."
        )

    expected_count = parse_count(trigger.inner_text())
    for attempt in range(3):
        trigger.click()
        dialog = current_visible_dialog(page)
        try:
            dialog.wait_for(state="visible", timeout=6000)
            time.sleep(1)
            if dialog_requests_authentication(dialog):
                ensure_logged_in_from_current_page(
                    page,
                    login_username=login_username,
                    login_password=login_password,
                    allow_terminal_input=allow_terminal_input,
                    resume_url=profile_url,
                )
                dismiss_instagram_dialogs(page, timeout_seconds=6.0)
                trigger = find_list_trigger(page, username, list_name)
                if trigger is None:
                    raise SystemExit(
                        f"Could not reopen the {list_name} list for {username} after login."
                    )
                continue
            return dialog, expected_count
        except PlaywrightTimeoutError:
            if ensure_logged_in_from_current_page(
                page,
                login_username=login_username,
                login_password=login_password,
                allow_terminal_input=allow_terminal_input,
                resume_url=profile_url,
            ):
                dismiss_instagram_dialogs(page, timeout_seconds=6.0)
                trigger = find_list_trigger(page, username, list_name)
                if trigger is None:
                    raise SystemExit(f"Could not reopen the {list_name} list for {username} after login.")
                continue

            dismiss_instagram_dialogs(page, timeout_seconds=6.0)
            if attempt == 0:
                continue

    raise SystemExit(f"Could not open the {list_name} list for {username}.")


def extract_dialog_usernames(page) -> list[str]:
    return page.evaluate(
        """(reserved) => {
            const dialogs = Array.from(document.querySelectorAll('div[role="dialog"]')).filter((dialog) => {
                const style = window.getComputedStyle(dialog);
                return style.display !== "none" && style.visibility !== "hidden" && !dialog.hidden;
            });
            const dialog = dialogs[dialogs.length - 1];
            if (!dialog) return [];

            const usernames = new Set();
            for (const link of dialog.querySelectorAll('a[href]')) {
                const href = link.getAttribute('href') || '';
                const match = href.match(/^\\/([^/?#]+)\\/$/);
                if (!match) continue;
                const username = match[1];
                if (!username || reserved.includes(username)) continue;
                usernames.add(username);
            }

            return Array.from(usernames);
        }""",
        sorted(RESERVED_PATHS),
    )


def scroll_dialog_once(page) -> dict | None:
    return page.evaluate(
        """() => {
            const dialogs = Array.from(document.querySelectorAll('div[role="dialog"]')).filter((dialog) => {
                const style = window.getComputedStyle(dialog);
                return style.display !== "none" && style.visibility !== "hidden" && !dialog.hidden;
            });
            const dialog = dialogs[dialogs.length - 1];
            if (!dialog) return null;

            const candidates = [dialog, ...dialog.querySelectorAll('*')];
            let scrollBox = dialog;
            for (const element of candidates) {
                if (element.scrollHeight > element.clientHeight + 20) {
                    if (element.scrollHeight > scrollBox.scrollHeight) {
                        scrollBox = element;
                    }
                }
            }

            scrollBox.scrollTop = scrollBox.scrollHeight;
            return {
                scrollHeight: scrollBox.scrollHeight,
                scrollTop: scrollBox.scrollTop,
            };
        }"""
    )


def load_all_dialog_items(page, list_name: str, expected_count: int | None) -> list[str]:
    stable_rounds = 0
    previous_height = -1
    previous_count = -1
    latest_usernames: list[str] = []

    for _ in range(300):
        latest_usernames = extract_dialog_usernames(page)
        metrics = scroll_dialog_once(page)
        if metrics is None:
            raise SystemExit(f"The {list_name} dialog closed before scraping completed.")

        current_height = metrics["scrollHeight"]
        current_count = len(latest_usernames)

        print(f"{list_name.capitalize()} loaded: {current_count}", end="\r", flush=True)

        if expected_count is not None and current_count >= expected_count:
            stable_rounds += 1
        elif current_height == previous_height and current_count == previous_count:
            stable_rounds += 1
        else:
            stable_rounds = 0

        if stable_rounds >= 4:
            break

        previous_height = current_height
        previous_count = current_count
        time.sleep(1)

    print(" " * 60, end="\r", flush=True)
    return sorted(set(latest_usernames), key=str.casefold)


def close_dialog(page) -> None:
    page.keyboard.press("Escape")
    time.sleep(1)


def scrape_list(
    page,
    username: str,
    list_name: str,
    *,
    login_username: str | None,
    login_password: str | None,
    allow_terminal_input: bool,
) -> list[str]:
    _, expected_count = open_list_dialog(
        page,
        username,
        list_name,
        login_username=login_username,
        login_password=login_password,
        allow_terminal_input=allow_terminal_input,
    )
    usernames = load_all_dialog_items(page, list_name, expected_count)
    close_dialog(page)
    return usernames


def run_scrape(
    username: str | None = None,
    output_dir: Path = DEFAULT_FOLLOWERS_PATH.parent,
    profile_dir: Path = DEFAULT_BROWSER_PROFILE_DIR,
    browser_executable: Path | None = None,
    allow_terminal_input: bool = True,
    login_username: str | None = None,
    login_password: str | None = None,
) -> tuple[Path, Path]:
    resolved_browser = resolve_browser_executable(browser_executable)

    with sync_playwright() as playwright:
        context, page = launch_persistent_chromium(
            playwright,
            profile_dir=profile_dir,
            browser_executable=resolved_browser,
        )

        try:
            wait_for_login(
                page,
                login_username=(login_username or username or "").strip() or None,
                login_password=login_password,
                allow_terminal_input=allow_terminal_input,
            )
            effective_login_username = (login_username or username or "").strip() or None
            resolved_username = resolve_account_username(
                page,
                username,
                login_username=effective_login_username,
                login_password=login_password,
                allow_terminal_input=allow_terminal_input,
            )
            print(f"Using Instagram account: {resolved_username}")

            followers = scrape_list(
                page,
                resolved_username,
                "followers",
                login_username=effective_login_username or resolved_username,
                login_password=login_password,
                allow_terminal_input=allow_terminal_input,
            )
            following = scrape_list(
                page,
                resolved_username,
                "following",
                login_username=effective_login_username or resolved_username,
                login_password=login_password,
                allow_terminal_input=allow_terminal_input,
            )
        finally:
            context.close()

    followers_path = output_dir / DEFAULT_FOLLOWERS_PATH.name
    following_path = output_dir / DEFAULT_FOLLOWING_PATH.name
    write_json(followers_path, followers)
    write_json(following_path, following)

    print(f"Wrote {len(followers)} followers to {followers_path}")
    print(f"Wrote {len(following)} following to {following_path}")
    return followers_path, following_path
