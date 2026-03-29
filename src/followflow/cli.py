from __future__ import annotations

import argparse
from pathlib import Path

from followflow.common import (
    DEFAULT_BROWSER_PROFILE_DIR,
    DEFAULT_EXPORT_SEARCH_ROOT,
    DEFAULT_FOLLOWERS_PATH,
    DEFAULT_FOLLOWING_PATH,
    DEFAULT_NON_MUTUALS_PATH,
    DEFAULT_REVIEW_LOG_PATH,
    DEFAULT_REVIEW_STATE_PATH,
)
from followflow.compare import run_compare
from followflow.export_parser import run_extract
from followflow.review import run_review
from followflow.scrape import run_scrape


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="followflow",
        description="Prepare follower data and review non-mutual profiles in a guided desktop workflow.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract clean followers/following lists from an Instagram export ZIP.",
    )
    extract_parser.add_argument("--zip", dest="zip_path", default=None, help="Path to an Instagram export ZIP.")
    extract_parser.add_argument(
        "--search-root",
        default=str(DEFAULT_EXPORT_SEARCH_ROOT),
        help="Where to search for the newest instagram-*.zip when --zip is omitted.",
    )
    extract_parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_FOLLOWERS_PATH.parent),
        help="Directory where followers.json and following.json will be written.",
    )

    compare_parser = subparsers.add_parser(
        "compare",
        help="Generate non_mutuals.json from followers and following data.",
    )
    compare_parser.add_argument(
        "--followers",
        default=str(DEFAULT_FOLLOWERS_PATH),
        help="Path to followers data.",
    )
    compare_parser.add_argument(
        "--following",
        default=str(DEFAULT_FOLLOWING_PATH),
        help="Path to following data.",
    )
    compare_parser.add_argument(
        "--output",
        default=str(DEFAULT_NON_MUTUALS_PATH),
        help="Path to write non_mutuals.json.",
    )

    scrape_parser = subparsers.add_parser(
        "scrape",
        help="Scrape followers/following from a logged-in Instagram browser session.",
    )
    scrape_parser.add_argument(
        "--username",
        default=None,
        help="Instagram username to scrape. If omitted, the tool tries to detect it from the logged-in session.",
    )
    scrape_parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_FOLLOWERS_PATH.parent),
        help="Directory where followers.json and following.json will be written.",
    )
    scrape_parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_BROWSER_PROFILE_DIR),
        help="Path to the persistent browser profile used by the managed browser.",
    )
    scrape_parser.add_argument(
        "--browser",
        default=None,
        help="Optional explicit path to a Chromium-based browser executable.",
    )

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Run zip extraction or browser scraping, then compare.",
    )
    prepare_parser.add_argument(
        "--source",
        choices=("zip", "scrape"),
        default="zip",
        help="Where followers/following should come from.",
    )
    prepare_parser.add_argument("--zip", dest="zip_path", default=None, help="Path to an Instagram export ZIP.")
    prepare_parser.add_argument(
        "--search-root",
        default=str(DEFAULT_EXPORT_SEARCH_ROOT),
        help="Where to search for the newest instagram-*.zip when --zip is omitted.",
    )
    prepare_parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_FOLLOWERS_PATH.parent),
        help="Directory where followers.json, following.json, and non_mutuals.json will be written.",
    )
    prepare_parser.add_argument(
        "--username",
        default=None,
        help="Instagram username to scrape when --source scrape is used.",
    )
    prepare_parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_BROWSER_PROFILE_DIR),
        help="Path to the persistent browser profile used by the managed browser when --source scrape is used.",
    )
    prepare_parser.add_argument(
        "--browser",
        default=None,
        help="Optional explicit path to a Chromium-based browser executable when --source scrape is used.",
    )

    review_parser = subparsers.add_parser(
        "review",
        help="Open profiles one by one and auto-advance after you manually unfollow in the browser.",
    )
    review_parser.add_argument(
        "--input",
        default=str(DEFAULT_NON_MUTUALS_PATH),
        help="Path to non_mutuals.json or a text file with usernames/profile URLs.",
    )
    review_parser.add_argument(
        "--following-file",
        default=str(DEFAULT_FOLLOWING_PATH),
        help="Path to following.json that should be updated after the session.",
    )
    review_parser.add_argument(
        "--state",
        default=str(DEFAULT_REVIEW_STATE_PATH),
        help="Path to the review state file.",
    )
    review_parser.add_argument(
        "--log",
        default=str(DEFAULT_REVIEW_LOG_PATH),
        help="Path to the JSONL review log.",
    )
    review_parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_BROWSER_PROFILE_DIR),
        help="Path to the persistent browser profile used by the managed browser.",
    )
    review_parser.add_argument(
        "--browser",
        default=None,
        help="Optional explicit path to a Chromium-based browser executable.",
    )
    review_parser.add_argument(
        "--start-at",
        type=int,
        default=None,
        help="Override the resume index and start at a specific zero-based position.",
    )
    review_parser.add_argument(
        "--reset",
        action="store_true",
        help="Ignore saved review state and start again from index 0.",
    )
    review_parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Disable the local review control panel and use terminal controls only.",
    )
    review_parser.add_argument(
        "--no-terminal",
        action="store_true",
        help="Disable terminal commands and rely on the local review control panel only.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "extract":
        run_extract(
            zip_path=Path(args.zip_path).expanduser() if args.zip_path else None,
            search_root=Path(args.search_root).expanduser(),
            output_dir=Path(args.output_dir).expanduser(),
        )
        return 0

    if args.command == "compare":
        run_compare(
            followers_path=Path(args.followers).expanduser(),
            following_path=Path(args.following).expanduser(),
            output_path=Path(args.output).expanduser(),
        )
        return 0

    if args.command == "scrape":
        run_scrape(
            username=args.username,
            output_dir=Path(args.output_dir).expanduser(),
            profile_dir=Path(args.profile_dir).expanduser(),
            browser_executable=Path(args.browser).expanduser() if args.browser else None,
        )
        return 0

    if args.command == "prepare":
        output_dir = Path(args.output_dir).expanduser()
        if args.source == "zip":
            followers_path, following_path = run_extract(
                zip_path=Path(args.zip_path).expanduser() if args.zip_path else None,
                search_root=Path(args.search_root).expanduser(),
                output_dir=output_dir,
            )
        else:
            followers_path, following_path = run_scrape(
                username=args.username,
                output_dir=output_dir,
                profile_dir=Path(args.profile_dir).expanduser(),
                browser_executable=Path(args.browser).expanduser() if args.browser else None,
            )
        run_compare(
            followers_path=followers_path,
            following_path=following_path,
            output_path=output_dir / DEFAULT_NON_MUTUALS_PATH.name,
        )
        return 0

    if args.command == "review":
        run_review(
            input_path=Path(args.input).expanduser(),
            following_path=Path(args.following_file).expanduser(),
            state_path=Path(args.state).expanduser(),
            log_path=Path(args.log).expanduser(),
            profile_dir=Path(args.profile_dir).expanduser(),
            browser_executable=Path(args.browser).expanduser() if args.browser else None,
            start_at=args.start_at,
            reset=args.reset,
            use_ui=not args.no_ui,
            allow_terminal_input=not args.no_terminal,
        )
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
