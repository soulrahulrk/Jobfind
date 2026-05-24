from __future__ import annotations

import argparse

from .config import DB_PATH, RESUME_PATH
from .database import connect, get_profile, init_db, upsert_profile
from .profile import load_profile
from .scanners import run_scan


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Job Finder tasks")
    parser.add_argument("command", choices=["init", "scan"])
    args = parser.parse_args()

    with connect(DB_PATH) as conn:
        init_db(conn)
        if args.command == "init":
            profile = load_profile(RESUME_PATH)
            upsert_profile(conn, profile)
            print(f"Profile saved for {profile.get('name')}")
            return

        if not get_profile(conn):
            upsert_profile(conn, load_profile(RESUME_PATH))
        result = run_scan(conn, include_network=True)
        print(f"Stored {result['stored']} jobs")
        if result["errors"]:
            print("Source errors:")
            for error in result["errors"]:
                print(f"- {error}")


if __name__ == "__main__":
    main()
