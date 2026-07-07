#!/usr/bin/env python3
"""
Sherlock Runner Script
=======================

This script is executed as a standalone subprocess by the FastAPI backend
(`webapp/main.py`). It runs the core Sherlock username-search logic
(imported directly from the `sherlock_project` package that already lives
in this repository) and prints a single JSON object to stdout.

Running it as a separate process (instead of importing the logic inline
inside the web server) keeps the web server responsive and isolates any
crash/timeout in the scanning logic from the FastAPI process itself.

Usage:
    python sherlock_runner.py <username> [--timeout SECONDS]

Output (stdout):
    A single JSON object, always in the form:
    {
        "success": true | false,
        "username": "<username>",
        "total_found": <int>,
        "results": [
            {
                "site": "GitHub",
                "url": "https://github.com/<username>",
                "status": "Claimed"
            },
            ...
        ],
        "error": "<error message, only present when success is false>"
    }
"""

import argparse
import json
import os
import sys

# Make sure the repository root (which contains the `sherlock_project`
# package) is importable regardless of the current working directory the
# subprocess was launched from.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def build_error(message: str, username: str = "") -> dict:
    return {
        "success": False,
        "username": username,
        "total_found": 0,
        "results": [],
        "error": message,
    }


def run(username: str, timeout: int) -> dict:
    try:
        from sherlock_project.notify import QueryNotify
        from sherlock_project.result import QueryStatus
        from sherlock_project.sites import SitesInformation
        from sherlock_project.sherlock import sherlock
    except Exception as import_error:
        return build_error(
            f"Sherlock is not installed correctly: {import_error}", username
        )

    try:
        local_data_path = os.path.join(
            REPO_ROOT, "sherlock_project", "resources", "data.json"
        )
        sites = SitesInformation(local_data_path if os.path.exists(local_data_path) else None)
    except Exception as sites_error:
        return build_error(
            f"Failed to load Sherlock site list: {sites_error}", username
        )

    site_data = {site.name: site.information for site in sites}

    # Silent notifier: we don't need any console output from the core
    # engine, we only care about the returned results dictionary.
    query_notify = QueryNotify()

    try:
        results = sherlock(
            username=username,
            site_data=site_data,
            query_notify=query_notify,
            timeout=timeout,
        )
    except Exception as run_error:
        return build_error(f"Sherlock encountered an error: {run_error}", username)

    found = []
    for site_name, data in results.items():
        status_obj = data.get("status")
        if status_obj is not None and status_obj.status == QueryStatus.CLAIMED:
            found.append(
                {
                    "site": site_name,
                    "url": data.get("url_user", ""),
                    "status": str(status_obj.status),
                }
            )

    found.sort(key=lambda item: item["site"].lower())

    return {
        "success": True,
        "username": username,
        "total_found": len(found),
        "results": found,
    }


def main():
    parser = argparse.ArgumentParser(description="Run Sherlock and output JSON results.")
    parser.add_argument("username", help="Username to search for.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Per-request timeout in seconds (default: 30).",
    )
    args = parser.parse_args()

    username = args.username.strip()
    if not username:
        print(json.dumps(build_error("Username cannot be empty.")))
        sys.exit(0)

    output = run(username, args.timeout)
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
