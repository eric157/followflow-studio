from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from followflow.common import (
    DEFAULT_EXPORT_SEARCH_ROOT,
    DEFAULT_FOLLOWERS_PATH,
    DEFAULT_FOLLOWING_PATH,
    extract_usernames,
    write_json,
)


FOLLOWERS_MEMBER_SUFFIX = "connections/followers_and_following/followers_1.json"
FOLLOWING_MEMBER_SUFFIX = "connections/followers_and_following/following.json"


def find_latest_export_zip(search_root: Path) -> Path | None:
    candidates = sorted(
        search_root.rglob("instagram-*.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def find_member_name(zf: ZipFile, suffix: str) -> str | None:
    normalized_suffix = suffix.replace("\\", "/")
    for name in zf.namelist():
        if name.endswith(normalized_suffix):
            return name
    return None


def read_json_from_zip(zf: ZipFile, member_name: str):
    return json.loads(zf.read(member_name).decode("utf-8"))


def extract_from_zip(zip_path: Path) -> tuple[list[str], list[str]]:
    with ZipFile(zip_path) as zf:
        followers_member = find_member_name(zf, FOLLOWERS_MEMBER_SUFFIX)
        following_member = find_member_name(zf, FOLLOWING_MEMBER_SUFFIX)

        if followers_member is None or following_member is None:
            raise SystemExit(
                "The ZIP does not contain the expected Instagram followers/following files."
            )

        followers = extract_usernames(read_json_from_zip(zf, followers_member))
        following = extract_usernames(read_json_from_zip(zf, following_member))

    return followers, following


def run_extract(
    zip_path: Path | None = None,
    search_root: Path = DEFAULT_EXPORT_SEARCH_ROOT,
    output_dir: Path = DEFAULT_FOLLOWERS_PATH.parent,
) -> tuple[Path, Path]:
    resolved_zip_path = zip_path or find_latest_export_zip(search_root)
    if resolved_zip_path is None or not resolved_zip_path.exists():
        raise SystemExit(
            f"Could not find an Instagram export ZIP under {search_root}. "
            "Pass --zip with the full archive path."
        )

    followers, following = extract_from_zip(resolved_zip_path)
    followers_path = output_dir / DEFAULT_FOLLOWERS_PATH.name
    following_path = output_dir / DEFAULT_FOLLOWING_PATH.name

    write_json(followers_path, followers)
    write_json(following_path, following)

    print(f"Using export ZIP: {resolved_zip_path}")
    print(f"Wrote {len(followers)} followers to {followers_path}")
    print(f"Wrote {len(following)} following to {following_path}")
    return followers_path, following_path
