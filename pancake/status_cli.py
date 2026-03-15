"""
status_cli.py -- Quick CLI to check or push session status.

Usage:
    python -m pancake.status_cli              # read local status
    python -m pancake.status_cli --pull       # pull from remote, then display
    python -m pancake.status_cli --push       # push current status to remote
    python -m pancake.status_cli --json       # output raw JSON
"""

from __future__ import annotations

import argparse
import json

from pancake.session_status import SessionStatus


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Check Pancake session status across devices"
    )
    parser.add_argument(
        "--pull", action="store_true",
        help="Pull latest status from git remote before displaying",
    )
    parser.add_argument(
        "--push", action="store_true",
        help="Push current status to git remote",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Output raw JSON instead of formatted text",
    )
    args = parser.parse_args(argv)

    status = SessionStatus()

    if args.pull:
        status.pull()

    if args.push:
        status.push()
        print("Status pushed to remote.")
        return

    if args.as_json:
        data = status.read()
        if data is None:
            print("{}")
        else:
            print(json.dumps(data, indent=2))
    else:
        print(status.format())


if __name__ == "__main__":
    main()
