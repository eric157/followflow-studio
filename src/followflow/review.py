from __future__ import annotations

import queue
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from followflow.browser import launch_persistent_chromium, resolve_browser_executable, wait_for_login
from followflow.common import (
    DEFAULT_BROWSER_PROFILE_DIR,
    DEFAULT_FOLLOWING_PATH,
    DEFAULT_NON_MUTUALS_PATH,
    DEFAULT_REVIEW_LOG_PATH,
    DEFAULT_REVIEW_STATE_PATH,
    append_log,
    load_state,
    load_targets,
    normalize_target,
    normalize_username_key,
    save_state,
    update_following_file,
)
from followflow.review_ui import ALLOWED_COMMANDS, ReviewUiServer, ReviewUiState


@dataclass(frozen=True)
class ReviewTarget:
    username: str
    url: str


class CommandReader:
    def __init__(
        self,
        shared_queue: queue.SimpleQueue[str] | None = None,
        *,
        allow_terminal_input: bool = True,
    ) -> None:
        self._queue: queue.SimpleQueue[str] = shared_queue or queue.SimpleQueue()
        self._stop_event = threading.Event()
        self._allow_terminal_input = allow_terminal_input
        self._thread: threading.Thread | None = None
        if self._allow_terminal_input:
            self._thread = threading.Thread(target=self._read_loop, daemon=True)

    def start(self) -> None:
        if self._thread is not None:
            self._thread.start()

    def _read_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                command = input().strip().lower()
            except EOFError:
                return

            if self._stop_event.is_set():
                return
            if command:
                self.put(command[0])

    def put(self, command: str) -> None:
        value = command.strip().lower()[:1]
        if value in ALLOWED_COMMANDS:
            self._queue.put(value)

    def poll(self) -> str | None:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def stop(self) -> None:
        self._stop_event.set()


def extract_profile_preview(page, username: str) -> dict[str, str]:
    payload = page.evaluate(
        """(fallbackUsername) => {
            const image =
                document.querySelector('meta[property="og:image"]')?.content ||
                document.querySelector('header img')?.src ||
                "";

            const metaTitle =
                document.querySelector('meta[property="og:title"]')?.content ||
                document.title ||
                "";

            const headerTexts = Array.from(
                document.querySelectorAll("header h1, header h2, header section h1, header section h2")
            )
                .map((element) => (element.textContent || "").trim())
                .filter(Boolean);

            let displayName = "";
            for (const text of headerTexts) {
                if (text.toLowerCase() !== fallbackUsername.toLowerCase()) {
                    displayName = text;
                    break;
                }
            }

            if (!displayName && metaTitle.includes("(@")) {
                displayName = metaTitle.split("(@")[0].trim();
            }

            if (!displayName) {
                displayName = fallbackUsername;
            }

            return {
                username: fallbackUsername,
                display_name: displayName,
                profile_image_url: image,
            };
        }""",
        username,
    )
    return {
        "username": payload.get("username", username),
        "display_name": payload.get("display_name", username),
        "profile_image_url": payload.get("profile_image_url", ""),
    }


def snapshot_profile(page) -> dict[str, str | list[str]]:
    payload = page.evaluate(
        """() => {
            const text = document.body ? (document.body.innerText || "") : "";
            const buttonTexts = Array.from(
                document.querySelectorAll("button, [role='button']")
            )
                .map((element) => (element.innerText || element.textContent || "").trim())
                .filter(Boolean)
                .slice(0, 100);

            return {
                url: window.location.href,
                pageText: text.slice(0, 15000),
                buttonTexts,
            };
        }"""
    )

    return {
        "url": payload["url"],
        "page_text": payload["pageText"],
        "button_texts": payload["buttonTexts"],
    }


def classify_profile_state(snapshot: dict[str, str | list[str]]) -> str:
    page_text = str(snapshot["page_text"]).casefold()
    button_texts = {str(text).casefold() for text in snapshot["button_texts"]}

    if "try again later" in page_text or "we restrict certain activity" in page_text:
        return "rate_limited"
    if "sorry, this page isn't available." in page_text or "user not found" in page_text:
        return "not_found"
    if "following" in button_texts or "requested" in button_texts:
        return "following"
    if "follow back" in button_texts or "follow" in button_texts:
        return "not_following"
    return "unknown"


def click_follow_toggle(page, timeout_seconds: float = 20.0) -> str:
    def click_clickable_with_text(scope, selector: str, candidate_texts: list[str]) -> bool:
        clickable = scope.locator(selector)
        for text in candidate_texts:
            locator = clickable.filter(has_text=text).first
            if locator.count():
                locator.click()
                return True
        return False

    def click_follow_toggle_in_header(candidate_texts: list[str]) -> bool:
        header = page.locator("header").first
        if header.count():
            exact = re.compile(r"^\s*(%s)\s*$" % "|".join(re.escape(text) for text in candidate_texts), re.IGNORECASE)
            toggle = header.locator("button, [role='button']").filter(has_text=exact).first
            if toggle.count():
                toggle.click()
                return True
        return click_clickable_with_text(page, "button, [role='button']", candidate_texts)

    starting_state = wait_for_known_state(page, timeout_seconds=timeout_seconds)
    if starting_state in {"rate_limited", "not_found"}:
        return starting_state

    if starting_state == "following":
        if not click_follow_toggle_in_header(["Following", "Requested"]):
            return "unknown"

        overlay = page.locator("div[role='dialog'], div[role='menu'], div[aria-modal='true']").last
        try:
            overlay.wait_for(state="visible", timeout=8000)
        except PlaywrightTimeoutError:
            overlay = page

        try:
            overlay.locator("text=Unfollow").first.wait_for(state="visible", timeout=8000)
        except PlaywrightTimeoutError:
            pass

        did_click = click_clickable_with_text(overlay, "button, [role='button'], a", ["Unfollow"]) or click_clickable_with_text(
            page,
            "button, [role='button'], a",
            ["Unfollow"],
        )
        if not did_click:
            return "unknown"

        confirm = page.locator("div[role='dialog'], div[aria-modal='true']").last
        try:
            confirm.wait_for(state="visible", timeout=5000)
            click_clickable_with_text(confirm, "button, [role='button'], a", ["Unfollow"])
        except PlaywrightTimeoutError:
            pass

        return wait_for_known_state(page, timeout_seconds=timeout_seconds)

    if starting_state == "not_following":
        if click_follow_toggle_in_header(["Follow", "Follow back"]):
            return wait_for_known_state(page, timeout_seconds=timeout_seconds)
        return "unknown"

    return "unknown"


def wait_for_known_state(page, timeout_seconds: float = 20.0) -> str:
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        state = classify_profile_state(snapshot_profile(page))
        if state != "unknown":
            return state
        time.sleep(0.5)

    return "unknown"


def build_log_record(username: str, url: str, status: str, index: int, *, error: str | None = None) -> dict[str, str | int]:
    record: dict[str, str | int] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "username": username,
        "url": url,
        "status": status,
        "index": index,
    }
    if error:
        record["error"] = error
    return record


def update_ui_from_page(
    ui_state: ReviewUiState,
    page,
    *,
    username: str,
    index: int,
    total: int,
    state_name: str,
    message: str,
    last_action: str | None = None,
) -> None:
    try:
        preview = extract_profile_preview(page, username)
    except Exception:
        preview = {
            "username": username,
            "display_name": username,
            "profile_image_url": "",
        }

    ui_state.update(
        username=preview["username"],
        display_name=preview["display_name"],
        profile_image_url=preview["profile_image_url"],
        current_index=index,
        total=total,
        state=state_name,
        message=message,
        last_action=last_action or message,
    )


def wait_for_manual_unfollow_or_command(
    page,
    starting_state: str,
    command_reader: CommandReader,
    *,
    allow_terminal_input: bool,
) -> str:
    if allow_terminal_input:
        print(
            "Waiting: manually change the profile in Instagram, or type "
            "f=toggle follow, s=skip, r=reload, q=quit, u=mark unfollowed then press Enter."
        )
    else:
        print("Waiting for the profile state to change or for a control-panel action.")

    if starting_state == "not_following":
        return "already_not_following"
    if starting_state == "not_found":
        return "not_found"
    if starting_state == "rate_limited":
        return "rate_limited"

    while True:
        command = command_reader.poll()
        if command in ALLOWED_COMMANDS:
            return command

        current_state = classify_profile_state(snapshot_profile(page))
        if current_state == "not_following":
            return "u"
        if current_state == "rate_limited":
            return "rate_limited"

        time.sleep(0.5)


def resolve_start_index(
    targets_count: int,
    state_path: Path,
    start_at: int | None,
    reset: bool,
) -> int:
    if start_at is not None:
        return max(0, min(start_at, targets_count))

    if reset:
        return 0

    saved_state = load_state(state_path)
    saved_index = int(saved_state.get("next_index", 0))

    if saved_index >= targets_count:
        print(
            f"Saved review state at {state_path} is already at the end of the current list "
            f"({saved_index}/{targets_count}). Starting over from index 0."
        )
        return 0

    if saved_index > 0:
        print(f"Resuming from saved state {state_path} at index {saved_index}.")

    return max(0, min(saved_index, targets_count))


def run_review(
    input_path: Path = DEFAULT_NON_MUTUALS_PATH,
    following_path: Path = DEFAULT_FOLLOWING_PATH,
    state_path: Path = DEFAULT_REVIEW_STATE_PATH,
    log_path: Path = DEFAULT_REVIEW_LOG_PATH,
    profile_dir: Path = DEFAULT_BROWSER_PROFILE_DIR,
    browser_executable: Path | None = None,
    start_at: int | None = None,
    reset: bool = False,
    use_ui: bool = True,
    allow_terminal_input: bool = True,
    login_username: str | None = None,
    login_password: str | None = None,
    *,
    open_review_ui_in_system_browser: bool = False,
) -> None:
    if not use_ui and not allow_terminal_input:
        raise SystemExit("Review requires either terminal input or the local control panel.")

    raw_targets = load_targets(input_path)
    targets = [ReviewTarget(*normalize_target(item)) for item in raw_targets]
    if not targets:
        raise SystemExit("No targets found in the input file.")

    index = resolve_start_index(
        targets_count=len(targets),
        state_path=state_path,
        start_at=start_at,
        reset=reset,
    )

    resolved_browser = resolve_browser_executable(browser_executable)
    session_unfollowed: set[str] = set()
    stopped_early = False
    command_queue: queue.SimpleQueue[str] = queue.SimpleQueue()
    command_reader = CommandReader(command_queue, allow_terminal_input=allow_terminal_input)
    ui_state = ReviewUiState()
    ui_state.update(
        total=len(targets),
        current_index=index,
        state="starting",
        message="Launching the managed Instagram browser session.",
        last_action="Launching the managed Instagram browser session.",
    )
    ui_server = ReviewUiServer(ui_state, command_reader) if use_ui else None

    print(f"Loaded {len(targets)} profiles from {input_path}")
    print(f"Starting at index {index}")
    if resolved_browser is not None:
        print(f"Using browser: {resolved_browser}")
    print(f"Managed browser profile: {profile_dir}")
    if ui_server is not None:
        ui_server.start()
        if open_review_ui_in_system_browser:
            ui_server.open_browser()
        if ui_server.url:
            print(f"Local review UI: {ui_server.url}")

    with sync_playwright() as playwright:
        context, page = launch_persistent_chromium(
            playwright,
            profile_dir=profile_dir,
            browser_executable=resolved_browser,
        )

        try:
            if ui_server is not None and ui_server.url and not open_review_ui_in_system_browser:
                ui_page = context.new_page()
                try:
                    ui_page.goto(ui_server.url, wait_until="domcontentloaded", timeout=30000)
                    print("Review control panel opened in the managed browser (second tab). Switch tabs between Instagram and the panel.")
                except Exception as exc:
                    print(
                        f"Could not open the review panel inside the managed browser ({exc}). "
                        f"Open this URL in any browser: {ui_server.url}"
                    )

            ui_state.update(state="login", message="Checking Instagram login state.", last_action="Checking Instagram login state.")
            wait_for_login(
                page,
                login_username=login_username,
                login_password=login_password,
                allow_terminal_input=allow_terminal_input,
                status_callback=lambda message: ui_state.update(
                    state="login",
                    message=message,
                    last_action=message,
                ),
            )
            command_reader.start()

            while index < len(targets):
                target = targets[index]
                print(f"\nOpening {index + 1}/{len(targets)}: {target.username}")
                ui_state.update(
                    username=target.username,
                    display_name=target.username,
                    profile_image_url="",
                    current_index=index + 1,
                    total=len(targets),
                    state="loading",
                    message=f"Opening {target.username} in the managed browser.",
                    last_action=f"Opening {target.username}.",
                )

                try:
                    page.goto(target.url, wait_until="domcontentloaded", timeout=60000)
                    state_name = wait_for_known_state(page)
                    update_ui_from_page(
                        ui_state,
                        page,
                        username=target.username,
                        index=index + 1,
                        total=len(targets),
                        state_name=state_name,
                        message="Use the browser or control panel to continue this review.",
                    )
                except PlaywrightTimeoutError as exc:
                    append_log(
                        log_path,
                        build_log_record(target.username, target.url, "open_failed", index, error=str(exc)),
                    )
                    print(f"Open failed: {exc}")
                    ui_state.update(
                        current_index=index + 1,
                        total=len(targets),
                        state="open_failed",
                        message=f"Open failed for {target.username}: {exc}",
                        last_action=f"Open failed for {target.username}.",
                    )
                    index += 1
                    save_state(state_path, index)
                    continue

                while True:
                    action = wait_for_manual_unfollow_or_command(
                        page,
                        state_name,
                        command_reader,
                        allow_terminal_input=allow_terminal_input,
                    )

                    if action == "f":
                        ui_state.update(
                            current_index=index + 1,
                            total=len(targets),
                            state=state_name,
                            message="Applying the follow toggle on the current profile.",
                            last_action=f"Toggle requested for {target.username}.",
                        )
                        next_state = click_follow_toggle(page)
                        if next_state in {"following", "not_following", "rate_limited", "not_found"}:
                            state_name = next_state
                        update_ui_from_page(
                            ui_state,
                            page,
                            username=target.username,
                            index=index + 1,
                            total=len(targets),
                            state_name=state_name,
                            message="Follow state updated. Continue the review.",
                            last_action=f"Toggle completed for {target.username}.",
                        )
                        continue

                    if action == "r":
                        page.reload(wait_until="domcontentloaded", timeout=60000)
                        state_name = wait_for_known_state(page)
                        update_ui_from_page(
                            ui_state,
                            page,
                            username=target.username,
                            index=index + 1,
                            total=len(targets),
                            state_name=state_name,
                            message="Profile reloaded. Continue the review.",
                            last_action=f"Reloaded {target.username}.",
                        )
                        continue

                    if action == "q":
                        stopped_early = True
                        save_state(state_path, index)
                        print(f"Stopped at index {index}. Resume later with the same command.")
                        ui_state.update(
                            current_index=index,
                            total=len(targets),
                            state="stopped",
                            message="Review stopped. You can resume later from the saved state.",
                            last_action="Session stopped and progress saved.",
                        )
                        break

                    if action == "rate_limited":
                        append_log(log_path, build_log_record(target.username, target.url, "rate_limited", index))
                        stopped_early = True
                        save_state(state_path, index)
                        print("Instagram reported a rate limit. Stopping the session.")
                        ui_state.update(
                            current_index=index + 1,
                            total=len(targets),
                            state="rate_limited",
                            message="Instagram reported a rate limit. The review session was stopped.",
                            last_action="Instagram reported a rate limit.",
                        )
                        break

                    if action == "not_found":
                        status = "not_found"
                    elif action == "already_not_following":
                        status = "already_not_following"
                        session_unfollowed.add(normalize_username_key(target.username))
                    elif action == "u":
                        status = "unfollowed_manually"
                        session_unfollowed.add(normalize_username_key(target.username))
                    else:
                        status = "skipped"

                    append_log(log_path, build_log_record(target.username, target.url, status, index))
                    ui_state.update(
                        current_index=index + 1,
                        total=len(targets),
                        state=status,
                        message=f"{target.username}: {status.replace('_', ' ')}. Moving to the next profile.",
                        last_action=f"{target.username}: {status.replace('_', ' ')}.",
                    )

                    index += 1
                    save_state(state_path, index)
                    break

                if stopped_early:
                    break

        except KeyboardInterrupt:
            save_state(state_path, index)
            print("\nInterrupted. Progress has been saved.")
            ui_state.update(
                current_index=index,
                total=len(targets),
                state="interrupted",
                message="Review interrupted. Progress has been saved.",
                last_action="Review interrupted from the keyboard.",
            )
        finally:
            command_reader.stop()

            removed_count, backup_path = update_following_file(following_path, session_unfollowed)
            if removed_count:
                print(f"Updated {following_path}: removed {removed_count} manually unfollowed usernames.")
                if backup_path is not None:
                    print(f"Backup saved to {backup_path}")
                ui_state.update(
                    state="updated",
                    message=f"Updated following.json and removed {removed_count} manually unfollowed usernames.",
                    last_action=f"following.json updated with {removed_count} removals.",
                )
            elif session_unfollowed:
                print(f"No changes were written to {following_path}.")
                ui_state.update(
                    state="updated",
                    message="The session marked profiles as unfollowed, but following.json was not changed.",
                    last_action="The session marked profiles, but following.json did not change.",
                )

            context.close()
            if ui_server is not None:
                ui_server.stop()

    if not stopped_early and index >= len(targets):
        print("\nAll profiles processed.")
        save_state(state_path, len(targets))
