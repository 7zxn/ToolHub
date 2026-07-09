#!/usr/bin/env python3
"""
Photon Runner Script
======================

This script is executed as a standalone subprocess by the FastAPI backend
(`webapp/main.py`). It runs the vendored Photon OSINT crawler
(`photon_project/photon.py`) against a target URL and prints a single JSON
object with the crawl results to stdout.

Photon itself is a top-level CLI script (not a Python library), so it is
invoked exactly like the Sherlock CLI would be: as a subprocess, writing
its results to a temporary output directory as `exported.json`, which we
then read back and re-emit as a single clean JSON payload.

Usage:
    python photon_runner.py <url> [--timeout SECONDS] [--level LEVEL]

Output (stdout):
    A single JSON object, always in the form:
    {
        "success": true | false,
        "url": "<url>",
        "total_found": <int>,
        "results": [
            {"category": "internal", "value": "https://example.com/about"},
            {"category": "emails", "value": "contact@example.com"},
            ...
        ],
        "error": "<error message, only present when success is false>"
    }
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTON_DIR = os.path.join(BASE_DIR, "photon_project")
PHOTON_SCRIPT = os.path.join(PHOTON_DIR, "photon.py")

# Categories that are useful/interesting to surface in the UI, in the
# order we want them displayed.
CATEGORY_LABELS = {
    "internal": "روابط داخلية",
    "external": "روابط خارجية",
    "endpoints": "نقاط نهاية (Endpoints)",
    "files": "ملفات",
    "scripts": "ملفات JavaScript",
    "intel": "معلومات (Emails/Phones)",
    "custom": "بيانات مخصصة",
    "fuzzable": "روابط قابلة للفحص (Fuzzable)",
    "keys": "مفاتيح مكتشفة",
    "robots": "مسارات robots.txt",
}


def build_error(message: str, url: str = "") -> dict:
    return {
        "success": False,
        "url": url,
        "total_found": 0,
        "results": [],
        "error": message,
    }


def run(url: str, timeout: int, level: int) -> dict:
    if not os.path.exists(PHOTON_SCRIPT):
        return build_error("أداة Photon غير مثبتة بشكل صحيح على الخادم.", url)

    with tempfile.TemporaryDirectory(prefix="photon_") as output_dir:
        cmd = [
            sys.executable,
            PHOTON_SCRIPT,
            "-u",
            url,
            "-o",
            output_dir,
            "-e",
            "json",
            "-l",
            str(level),
            "-t",
            "20",
            "--timeout",
            str(timeout),
        ]

        try:
            process = subprocess.run(
                cmd,
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=timeout + 60,
            )
        except subprocess.TimeoutExpired:
            return build_error("انتهت مهلة الفحص. حاول مرة أخرى لاحقًا.", url)
        except Exception as run_error:
            return build_error(f"حدث خطأ أثناء تشغيل Photon: {run_error}", url)

        exported_path = os.path.join(output_dir, "exported.json")
        if not os.path.exists(exported_path):
            error_message = (process.stderr or process.stdout or "").strip()
            return build_error(
                error_message[-500:] if error_message else "لم يتم استلام أي نتائج من أداة Photon.",
                url,
            )

        try:
            with open(exported_path, "r", encoding="utf-8") as file:
                datasets = json.load(file)
        except Exception as parse_error:
            return build_error(f"تعذر قراءة نتائج Photon: {parse_error}", url)

    results = []
    for category, label in CATEGORY_LABELS.items():
        values = datasets.get(category) or []
        for value in values:
            if not value:
                continue
            results.append({"category": label, "value": str(value)})

    return {
        "success": True,
        "url": url,
        "total_found": len(results),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Run Photon and output JSON results.")
    parser.add_argument("url", help="Target URL to crawl.")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP request timeout in seconds.")
    parser.add_argument("--level", type=int, default=2, help="Crawl depth level.")
    args = parser.parse_args()

    url = args.url.strip()
    if not url:
        print(json.dumps(build_error("الرجاء إدخال رابط صالح.")))
        sys.exit(0)

    output = run(url, args.timeout, args.level)
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
