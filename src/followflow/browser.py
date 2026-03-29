from __future__ import annotations

import os
import re
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


INSTAGRAM_HOME_URL = "https://www.instagram.com/"
INSTAGRAM_LOGIN_URL = "https://www.instagram.com/accounts/login/"
DISMISS_TEXT_GROUPS = [
    ["Not now", "Maybe later", "Skip", "No thanks"],
    ["Only allow essential cookies", "Decline optional cookies", "Decline optional cookies and ads"],
    ["Close", "Cancel"],
]
POST_LOGIN_SETTLE_SECONDS = 12.0
LOG_IN_LABELS = ["Log in", "Log In"]
SIGN_UP_LABELS = ["Sign up", "Sign Up"]
AUTH_CHECK_PATH = "/accounts/edit/"
VERIFICATION_PATH_MARKERS = ("challenge", "checkpoint", "two_factor", "two-factor")
VERIFICATION_TEXT_MARKERS = (
    "two-factor authentication",
    "two factor authentication",
    "security code",
    "confirmation code",
    "confirm it's you",
    "confirm it is you",
    "approve login",
    "confirm your identity",
    "check your email",
    "check your phone",
    "enter the code",
    "enter code",
    "suspicious login attempt",
    "help us confirm",
)


def detect_browser_executable() -> Path | None:
    if sys.platform.startswith("win"):
        env_values = {
            "PROGRAMFILES": os.environ.get("PROGRAMFILES", ""),
            "PROGRAMFILES(X86)": os.environ.get("PROGRAMFILES(X86)", ""),
            "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
        }
        candidate_strings = [
            os.path.join(env_values["PROGRAMFILES"], "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(env_values["PROGRAMFILES(X86)"], "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(env_values["LOCALAPPDATA"], "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(env_values["PROGRAMFILES"], "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(env_values["PROGRAMFILES(X86)"], "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(env_values["LOCALAPPDATA"], "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(env_values["PROGRAMFILES"], "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(env_values["PROGRAMFILES(X86)"], "Microsoft", "Edge", "Application", "msedge.exe"),
        ]
        for candidate in candidate_strings:
            if candidate and Path(candidate).exists():
                return Path(candidate)
        return None

    if sys.platform == "darwin":
        candidate_strings = [
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
        for candidate in candidate_strings:
            if Path(candidate).exists():
                return Path(candidate)
        return None

    for candidate in ("brave-browser", "google-chrome", "microsoft-edge", "chromium"):
        resolved = shutil.which(candidate)
        if resolved:
            return Path(resolved)
    return None


def resolve_browser_executable(browser_executable: Path | None = None) -> Path | None:
    resolved_browser = browser_executable or detect_browser_executable()
    if resolved_browser is not None and not resolved_browser.exists():
        raise SystemExit(f"Browser executable not found: {resolved_browser}")
    return resolved_browser


def launch_persistent_chromium(playwright, profile_dir: Path, browser_executable: Path | None = None):
    profile_dir.mkdir(parents=True, exist_ok=True)
    launch_kwargs = {
        "user_data_dir": str(profile_dir),
        "headless": False,
    }
    if browser_executable is not None:
        launch_kwargs["executable_path"] = str(browser_executable)

    context = playwright.chromium.launch_persistent_context(**launch_kwargs)
    page = context.pages[0] if context.pages else context.new_page()
    return context, page


def login_form_visible(page) -> bool:
    username_input = page.locator("input[name='username']").first
    password_input = page.locator("input[name='password']").first
    return bool(username_input.count() and password_input.count())


def auth_prompt_visible(page) -> bool:
    if login_form_visible(page):
        return True

    login_exact = re.compile(r"^\s*(?:%s)\s*$" % "|".join(re.escape(label) for label in LOG_IN_LABELS), re.IGNORECASE)
    signup_exact = re.compile(r"^\s*(?:%s)\s*$" % "|".join(re.escape(label) for label in SIGN_UP_LABELS), re.IGNORECASE)

    dialog = page.locator("div[role='dialog']:visible").last
    if dialog.count():
        login_action = dialog.locator("button:visible, a:visible, [role='button']:visible").filter(has_text=login_exact).first
        signup_action = dialog.locator("button:visible, a:visible, [role='button']:visible").filter(has_text=signup_exact).first
        if login_action.count() or signup_action.count():
            return True

    try:
        page_text = (page.locator("body").inner_text(timeout=1500) or "").casefold()
    except PlaywrightTimeoutError:
        page_text = ""

    auth_markers = (
        "log in to continue",
        "sign up to see photos and videos",
        "log in to see photos and videos",
    )
    if any(marker in page_text for marker in auth_markers):
        return True

    login_action = page.locator("button:visible, a:visible, [role='button']:visible").filter(has_text=login_exact).first
    signup_action = page.locator("button:visible, a:visible, [role='button']:visible").filter(has_text=signup_exact).first
    return bool(login_action.count() and signup_action.count())


def dialog_requests_authentication(dialog) -> bool:
    login_exact = re.compile(r"^\s*(?:%s)\s*$" % "|".join(re.escape(label) for label in LOG_IN_LABELS), re.IGNORECASE)
    signup_exact = re.compile(r"^\s*(?:%s)\s*$" % "|".join(re.escape(label) for label in SIGN_UP_LABELS), re.IGNORECASE)
    login_action = dialog.locator("button:visible, a:visible, [role='button']:visible").filter(has_text=login_exact).first
    signup_action = dialog.locator("button:visible, a:visible, [role='button']:visible").filter(has_text=signup_exact).first
    return bool(login_action.count() and signup_action.count())


def _click_matching_button(page, labels: list[str]) -> str | None:
    exact = re.compile(r"^\s*(?:%s)\s*$" % "|".join(re.escape(label) for label in labels), re.IGNORECASE)
    locator = page.locator("button, [role='button']").filter(has_text=exact).first
    if locator.count():
        try:
            locator.click(timeout=1500)
            return labels[0]
        except PlaywrightTimeoutError:
            return None
    return None


def _click_close_control(page) -> str | None:
    close_selector = "button[aria-label='Close'], [role='button'][aria-label='Close'], button[title='Close']"
    locator = page.locator(close_selector).first
    if locator.count():
        try:
            locator.click(timeout=1500)
            return "Close"
        except PlaywrightTimeoutError:
            return None
    return None


def dismiss_instagram_dialogs(
    page,
    *,
    timeout_seconds: float = POST_LOGIN_SETTLE_SECONDS,
    status_callback=None,
) -> list[str]:
    dismissed: list[str] = []
    deadline = time.time() + timeout_seconds
    idle_rounds = 0

    while time.time() < deadline:
        clicked = None
        for labels in DISMISS_TEXT_GROUPS:
            clicked = _click_matching_button(page, labels)
            if clicked is not None:
                break

        if clicked is None:
            clicked = _click_close_control(page)

        if clicked is not None:
            dismissed.append(clicked)
            idle_rounds = 0
            if status_callback is not None:
                status_callback(f"Clearing Instagram prompt: {clicked}")
            time.sleep(0.8)
            continue

        idle_rounds += 1
        if idle_rounds >= 3:
            break
        time.sleep(0.8)

    return dismissed


def settle_after_login(page, *, status_callback=None) -> list[str]:
    return dismiss_instagram_dialogs(page, timeout_seconds=POST_LOGIN_SETTLE_SECONDS, status_callback=status_callback)


def build_login_url(resume_url: str | None = None) -> str:
    parsed = urlparse(INSTAGRAM_LOGIN_URL)
    if parsed.scheme not in {"http", "https"}:
        return INSTAGRAM_LOGIN_URL

    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if resume_url:
        resume_parsed = urlparse(resume_url)
        query_items["next"] = resume_parsed.path or "/"

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query_items),
            parsed.fragment,
        )
    )


def build_auth_check_url() -> str | None:
    parsed = urlparse(INSTAGRAM_LOGIN_URL)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return urlunparse((parsed.scheme, parsed.netloc, AUTH_CHECK_PATH, "", "", ""))
    return None


def current_page_is_login_route(page) -> bool:
    current_path = urlparse(page.url).path.rstrip("/").casefold()
    login_path = urlparse(INSTAGRAM_LOGIN_URL).path.rstrip("/").casefold()
    return bool(login_path and current_path == login_path)


def login_still_requires_user_steps(page) -> bool:
    path = urlparse(page.url).path.casefold()
    if any(marker in path for marker in VERIFICATION_PATH_MARKERS):
        return True

    try:
        page_text = (page.locator("body").inner_text(timeout=1500) or "").casefold()
    except PlaywrightTimeoutError:
        return False
    return any(marker in page_text for marker in VERIFICATION_TEXT_MARKERS)


def authenticated_session_ready(page, *, status_callback=None) -> bool:
    # Avoid touching the visible page while the user is actively logging in.
    if login_form_visible(page) or current_page_is_login_route(page) or auth_prompt_visible(page) or login_still_requires_user_steps(page):
        return False

    dismiss_instagram_dialogs(page, timeout_seconds=4.0, status_callback=status_callback)

    probe_url = build_auth_check_url()
    if not probe_url:
        return True

    try:
        response = page.context.request.get(
            probe_url,
            max_redirects=10,
            timeout=10_000,
            headers={"Cache-Control": "no-store"},
        )
    except PlaywrightTimeoutError:
        return False
    except Exception:
        return False

    try:
        body = (response.text() or "")[:2000]
    except PlaywrightTimeoutError:
        return False
    except Exception:
        body = ""

    normalized_body = str(body).casefold()
    if any(marker in normalized_body for marker in VERIFICATION_TEXT_MARKERS):
        return False

    current_path = urlparse(str(getattr(response, "url", "") or "")).path.rstrip("/").casefold()
    expected_path = urlparse(probe_url).path.rstrip("/").casefold()
    if current_path == expected_path:
        return True

    return False


def ensure_logged_in_from_current_page(
    page,
    *,
    login_username: str | None = None,
    login_password: str | None = None,
    allow_terminal_input: bool = True,
    status_callback=None,
    resume_url: str | None = None,
) -> bool:
    if not auth_prompt_visible(page):
        return False

    if status_callback is not None:
        status_callback("Instagram requested a login before continuing. Finish the login in the browser and FollowFlow will retry automatically.")
    print("Instagram requested a login before continuing. Finish the login in the browser and FollowFlow will retry automatically.")

    wait_for_login(
        page,
        login_username=login_username,
        login_password=login_password,
        allow_terminal_input=allow_terminal_input,
        status_callback=status_callback,
        force_login=True,
        resume_url=resume_url,
    )
    return True


def attempt_login(
    page,
    *,
    login_username: str,
    login_password: str,
    status_callback=None,
) -> bool:
    if status_callback is not None:
        status_callback("Signing into Instagram with the provided credentials.")
    print("Signing into Instagram with the provided credentials.")

    page.locator("input[name='username']").first.fill(login_username)
    page.locator("input[name='password']").first.fill(login_password)
    submit = page.locator("button[type='submit']").first
    if submit.count():
        submit.click()
    else:
        page.locator("input[name='password']").first.press("Enter")

    deadline = time.time() + 30
    while time.time() < deadline:
        time.sleep(1.2)
        if not login_form_visible(page):
            settle_after_login(page, status_callback=status_callback)
            return True

        try:
            page_text = (page.locator("body").inner_text(timeout=2000) or "").casefold()
        except PlaywrightTimeoutError:
            page_text = ""
        if "incorrect password" in page_text or "password was incorrect" in page_text:
            raise SystemExit("Instagram login failed. Check the login username and password and try again.")

    return False


def wait_for_login(
    page,
    *,
    login_username: str | None = None,
    login_password: str | None = None,
    allow_terminal_input: bool = True,
    status_callback=None,
    timeout_seconds: float = 1800.0,
    force_login: bool = False,
    resume_url: str | None = None,
) -> None:
    target_url = build_login_url(resume_url)
    page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
    time.sleep(2)
    dismiss_instagram_dialogs(page, timeout_seconds=6.0, status_callback=status_callback)

    if authenticated_session_ready(page, status_callback=status_callback):
        if resume_url and page.url.rstrip("/") != resume_url.rstrip("/"):
            page.goto(resume_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
            dismiss_instagram_dialogs(page, timeout_seconds=6.0, status_callback=status_callback)
        return

    attempted_auto_login = False
    if login_password and (login_username or allow_terminal_input is False):
        attempted_auto_login = True
        effective_login = (login_username or "").strip()
        if effective_login:
            attempt_login(
                page,
                login_username=effective_login,
                login_password=login_password,
                status_callback=status_callback,
            )

    if authenticated_session_ready(page, status_callback=status_callback):
        if resume_url and page.url.rstrip("/") != resume_url.rstrip("/"):
            page.goto(resume_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
            dismiss_instagram_dialogs(page, timeout_seconds=6.0, status_callback=status_callback)
        return

    if attempted_auto_login:
        message = "Instagram needs extra verification in the browser. Finish the login there and FollowFlow will continue automatically."
    else:
        message = "Log into Instagram in the opened browser window. FollowFlow is waiting and will continue automatically."
    if status_callback is not None:
        status_callback(message)
    print(message)

    if allow_terminal_input and sys.stdin is not None and sys.stdin.isatty():
        print("Press Enter here after Instagram finishes logging in.")
        try:
            input()
        except EOFError:
            pass
        time.sleep(1)
        if authenticated_session_ready(page, status_callback=status_callback):
            if resume_url and page.url.rstrip("/") != resume_url.rstrip("/"):
                page.goto(resume_url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(2)
                dismiss_instagram_dialogs(page, timeout_seconds=6.0, status_callback=status_callback)
            return

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        time.sleep(2)
        if authenticated_session_ready(page, status_callback=status_callback):
            if resume_url and page.url.rstrip("/") != resume_url.rstrip("/"):
                page.goto(resume_url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(2)
                dismiss_instagram_dialogs(page, timeout_seconds=6.0, status_callback=status_callback)
            return

    raise SystemExit("Timed out waiting for the Instagram login to finish.")
