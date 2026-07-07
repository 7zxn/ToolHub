#!/usr/bin/env python3
"""
Maigret Runner Script
=======================

This script is executed as a standalone subprocess by the FastAPI backend
(`webapp/main.py`). It runs Maigret (https://github.com/soxoj/maigret), a
username OSINT tool similar in spirit to Sherlock but with richer profile
extraction, against a target username and prints a single JSON object with
the results to stdout.

Maigret is installed as a regular Python package (`pip install maigret`),
and is invoked here as `python -m maigret` writing an NDJSON report to a
temporary output directory, which we then read back and re-emit as a single
clean JSON payload (mirroring the Sherlock/Photon runner pattern).

Usage:
    python maigret_runner.py <username> [--timeout SECONDS] [--top-sites N]

Output (stdout):
    A single JSON object, always in the form:
    {
        "success": true | false,
        "username": "<username>",
        "total_found": <int>,
        "results": [
            {"site": "GitHub", "url": "https://github.com/<username>", "status": "Claimed"},
            ...
        ],
        "error": "<error message, only present when success is false>"
    }
"""

import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile


def build_error(message: str, username: str = "") -> dict:
    return {
        "success": False,
        "username": username,
        "total_found": 0,
        "results": [],
        "error": message,
    }


def run(username: str, timeout: int, top_sites: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="maigret_") as output_dir:
        cmd = [
            sys.executable,
            "-m",
            "maigret",
            username,
            "-J",
            "ndjson",
            "-fo",
            output_dir,
            "--no-recursion",
            "--no-extracting",
            "--no-progressbar",
            "--no-color",
            "--no-autoupdate",
            "--timeout",
            str(timeout),
            "--top-sites",
            str(top_sites),
        ]

        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 60,
            )
        except subprocess.TimeoutExpired:
            return build_error("انتهت مهلة البحث. حاول مرة أخرى لاحقًا.", username)
        except Exception as run_error:
            return build_error(f"حدث خطأ أثناء تشغيل Maigret: {run_error}", username)

        report_files = glob.glob(os.path.join(output_dir, "report_*_ndjson.json"))
        if not report_files:
            error_message = (process.stderr or process.stdout or "").strip()
            return build_error(
                error_message[-500:] if error_message else "لم يتم استلام أي نتائج من أداة Maigret.",
                username,
            )

        found = []
        for report_file in report_files:
            try:
                with open(report_file, "r", encoding="utf-8") as file:
                    for line in file:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        status = (entry.get("status") or {}).get("status", "")
                        if status != "Claimed":
                            continue

                        site_info = entry.get("site") or {}
                        site_name = (
                            entry.get("status", {}).get("site_name")
                            or site_info.get("name")
                            or "Unknown"
                        )
                        url = entry.get("url_user") or entry.get("status", {}).get("url", "")
                        if not url:
                            continue

                        found.append(
                            {
                                "site": str(site_name),
                                "url": str(url),
                                "status": "Claimed",
                            }
                        )
            except Exception:
                continue

    seen = set()
    unique_found = []
    for item in found:
        key = (item["site"], item["url"])
        if key in seen:
            continue
        seen.add(key)
        unique_found.append(item)

    unique_found.sort(key=lambda item: item["site"].lower())

    return {
        "success": True,
        "username": username,
        "total_found": len(unique_found),
        "results": unique_found,
    }


def main():
    parser = argparse.ArgumentParser(description="Run Maigret and output JSON results.")
    parser.add_argument("username", help="Username to search for.")
    parser.add_argument("--timeout", type=int, default=15, help="Per-request timeout in seconds.")
    parser.add_argument("--top-sites", type=int, default=500, help="Number of top-ranked sites to scan.")
    args = parser.parse_args()

    username = args.username.strip()
    if not username:
        print(json.dumps(build_error("الرجاء إدخال اسم مستخدم.")))
        sys.exit(0)

    output = run(username, args.timeout, args.top_sites)
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
