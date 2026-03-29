from __future__ import annotations

from pathlib import Path

from followflow.common import (
    DEFAULT_FOLLOWERS_PATH,
    DEFAULT_FOLLOWING_PATH,
    DEFAULT_NON_MUTUALS_PATH,
    extract_usernames,
    read_json,
    write_json,
)


def run_compare(
    followers_path: Path = DEFAULT_FOLLOWERS_PATH,
    following_path: Path = DEFAULT_FOLLOWING_PATH,
    output_path: Path = DEFAULT_NON_MUTUALS_PATH,
) -> list[str]:
    if not followers_path.exists():
        raise SystemExit(f"Followers file not found: {followers_path}")
    if not following_path.exists():
        raise SystemExit(f"Following file not found: {following_path}")

    followers = set(extract_usernames(read_json(followers_path)))
    following = set(extract_usernames(read_json(following_path)))
    non_mutuals = sorted(following - followers, key=str.casefold)

    write_json(output_path, non_mutuals)

    print(f"Followers loaded: {len(followers)} from {followers_path}")
    print(f"Following loaded: {len(following)} from {following_path}")
    print(f"Saved {len(non_mutuals)} usernames to {output_path}")
    return non_mutuals
