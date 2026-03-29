from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


APP_NAME = "FollowFlow"
APP_REPO_NAME = "followflow-studio"
DEFAULT_DATA_DIR = Path("data")
DEFAULT_EXPORT_SEARCH_ROOT = Path.home() / "Downloads"
DEFAULT_EXPORTS_DIR = DEFAULT_DATA_DIR / "exports"
DEFAULT_PROCESSED_DIR = DEFAULT_DATA_DIR / "processed"
DEFAULT_RUNTIME_DIR = DEFAULT_DATA_DIR / "runtime"
DEFAULT_FOLLOWERS_PATH = DEFAULT_PROCESSED_DIR / "followers.json"
DEFAULT_FOLLOWING_PATH = DEFAULT_PROCESSED_DIR / "following.json"
DEFAULT_NON_MUTUALS_PATH = DEFAULT_PROCESSED_DIR / "non_mutuals.json"
DEFAULT_REVIEW_STATE_PATH = DEFAULT_RUNTIME_DIR / "review_state.json"
DEFAULT_REVIEW_LOG_PATH = DEFAULT_RUNTIME_DIR / "review_log.jsonl"
DEFAULT_BROWSER_PROFILE_DIR = DEFAULT_RUNTIME_DIR / "browser-profile"
INSTAGRAM_BASE = "https://www.instagram.com/"


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    ensure_directory(path.parent)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def normalize_username_key(value: str) -> str:
    return value.strip().lstrip("@").casefold()


def unique_in_order(items: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for item in items:
        cleaned = item.strip()
        if not cleaned:
            continue
        key = normalize_username_key(cleaned)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def extract_usernames(payload: Any) -> list[str]:
    if isinstance(payload, list):
        if not payload:
            return []
        if all(isinstance(item, str) for item in payload):
            return unique_in_order([item for item in payload if item.strip()])

        usernames = []
        for item in payload:
            usernames.extend(extract_usernames(item))
        return unique_in_order(usernames)

    if isinstance(payload, dict):
        if "relationships_following" in payload:
            return extract_usernames(payload["relationships_following"])
        if isinstance(payload.get("title"), str) and payload["title"].strip():
            return [payload["title"].strip()]
        if "string_list_data" in payload and isinstance(payload["string_list_data"], list):
            values = []
            for entry in payload["string_list_data"]:
                if isinstance(entry, dict) and isinstance(entry.get("value"), str):
                    value = entry["value"].strip()
                    if value:
                        values.append(value)
            return unique_in_order(values)

        usernames = []
        for value in payload.values():
            usernames.extend(extract_usernames(value))
        return unique_in_order(usernames)

    return []


def load_targets(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"Input file not found: {path}")

    if path.suffix.lower() == ".json":
        payload = read_json(path)
        if not isinstance(payload, list):
            raise SystemExit("JSON input must be a list of usernames or profile URLs.")
        return [str(item).strip() for item in payload if str(item).strip()]

    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def normalize_target(raw_value: str) -> tuple[str, str]:
    value = raw_value.strip()
    if value.startswith("http://") or value.startswith("https://"):
        url = value.rstrip("/") + "/"
        username = url.rstrip("/").split("/")[-1]
        return username, url

    username = value.lstrip("@")
    return username, f"{INSTAGRAM_BASE}{username}/"


def load_state(path: Path) -> dict[str, int]:
    if not path.exists():
        return {"next_index": 0}

    try:
        payload = read_json(path)
    except json.JSONDecodeError:
        return {"next_index": 0}

    if not isinstance(payload, dict):
        return {"next_index": 0}
    return {"next_index": int(payload.get("next_index", 0))}


def save_state(path: Path, next_index: int) -> None:
    write_json(path, {"next_index": next_index})


def append_log(path: Path, record: dict[str, Any]) -> None:
    ensure_directory(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_following_usernames(path: Path) -> list[str]:
    if not path.exists():
        return []
    return extract_usernames(read_json(path))


def update_following_file(path: Path, removed_usernames: set[str]) -> tuple[int, Path | None]:
    if not removed_usernames or not path.exists():
        return 0, None

    existing = load_following_usernames(path)
    if not existing:
        return 0, None

    backup_path = path.with_suffix(path.suffix + ".bak")
    if not backup_path.exists():
        shutil.copy2(path, backup_path)

    filtered = [
        username
        for username in existing
        if normalize_username_key(username) not in removed_usernames
    ]

    removed_count = len(existing) - len(filtered)
    write_json(path, filtered)
    return removed_count, backup_path
