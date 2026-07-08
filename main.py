"""
ToolHub - FastAPI Backend
================================

A minimal single-page web interface that hosts two OSINT tools:
  * Sherlock  -- searches a username across hundreds of social networks.
  * Photon    -- crawls a URL and extracts links, endpoints, emails, etc.

Responsibilities of this module:
  * Serve the static frontend (HTML/CSS/JS) found in `webapp/static`.
  * Expose two JSON API endpoints:
      - `POST /api/search` runs Sherlock (`webapp/sherlock_runner.py`).
      - `POST /api/photon` runs Photon (`webapp/photon_runner.py`).
    Both run the underlying tool in a subprocess and return parsed JSON
    results to the browser.

Run locally with:
    uvicorn webapp.main:app --host 0.0.0.0 --port 5000
"""

import asyncio
import json
import os
import re
import sys

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
SHERLOCK_RUNNER_SCRIPT = os.path.join(BASE_DIR, "sherlock_runner.py")
PHOTON_RUNNER_SCRIPT = os.path.join(BASE_DIR, "photon_runner.py")
MAIGRET_RUNNER_SCRIPT = os.path.join(BASE_DIR, "maigret_runner.py")

# Sherlock/Maigret query hundreds of sites concurrently; Photon crawls a
# live website. All of these can legitimately take a while, so we cap how
# long we let the subprocess run before giving up and reporting a timeout
# error.
SHERLOCK_TIMEOUT_SECONDS = 90
PHOTON_TIMEOUT_SECONDS = 60
MAIGRET_TIMEOUT_SECONDS = 90

# Basic sanity check for usernames: letters, numbers, dot, underscore, dash.
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
# Basic sanity check for target URLs/domains typed by the user.
URL_PATTERN = re.compile(r"^[A-Za-z0-9_.\-:/?=&%~#]{1,2048}$")

app = FastAPI(title="ToolHub")

# The Replit preview loads this app through a proxied iframe on a
# different host/origin than "localhost", so we don't restrict allowed
# hosts here. FastAPI/Starlette do not enforce host header checks by
# default (unlike some frameworks), which already makes this work behind
# the Replit proxy without extra configuration.


class SearchRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)


class SearchResult(BaseModel):
    site: str
    url: str
    status: str


class SearchResponse(BaseModel):
    success: bool
    username: str
    total_found: int
    results: list[SearchResult] = []
    error: str | None = None


class PhotonRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)


class PhotonResult(BaseModel):
    category: str
    value: str


class PhotonResponse(BaseModel):
    success: bool
    url: str
    total_found: int
    results: list[PhotonResult] = []
    error: str | None = None


class MaigretRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)


class MaigretResult(BaseModel):
    site: str
    url: str
    status: str


class MaigretResponse(BaseModel):
    success: bool
    username: str
    total_found: int
    results: list[MaigretResult] = []
    error: str | None = None


async def run_subprocess_json(
    script_path: str,
    args: list[str],
    timeout_seconds: int,
    tool_label: str,
) -> dict:
    """Run a helper script as a subprocess and parse its final JSON line."""

    if not os.path.exists(script_path):
        raise HTTPException(
            status_code=500,
            detail=f"أداة {tool_label} غير مثبتة بشكل صحيح على الخادم.",
        )

    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            script_path,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise HTTPException(
                status_code=504,
                detail="انتهت مهلة البحث. حاول مرة أخرى لاحقًا.",
            )

    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="تعذر تشغيل الأداة. تأكد من تثبيت Python بشكل صحيح.",
        )

    if process.returncode not in (0, None):
        error_message = (
            stderr.decode("utf-8", errors="ignore").strip()
            or stdout.decode("utf-8", errors="ignore").strip()
            or f"حدث خطأ غير متوقع أثناء تشغيل {tool_label} (Exit Code: {process.returncode})."
        )
        # If it's a known success case but with non-zero code (sometimes happens with tools)
        # we check if we have valid JSON in stdout first
        raw_output = stdout.decode("utf-8", errors="ignore").strip()
        if raw_output:
            try:
                json.loads(raw_output.splitlines()[-1])
            except:
                raise HTTPException(status_code=500, detail=error_message)
        else:
            raise HTTPException(status_code=500, detail=error_message)

    raw_output = stdout.decode("utf-8", errors="ignore").strip()
    if not raw_output:
        error_message = (
            stderr.decode("utf-8", errors="ignore").strip()
            or f"لم يتم استلام أي نتائج من أداة {tool_label}."
        )
        raise HTTPException(status_code=500, detail=error_message)

    try:
        data = json.loads(raw_output.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        raise HTTPException(
            status_code=500,
            detail=f"تعذر قراءة نتائج {tool_label} (تنسيق JSON غير صالح).",
        )

    if not data.get("success"):
        raise HTTPException(
            status_code=500,
            detail=data.get("error", f"حدث خطأ غير متوقع أثناء تشغيل {tool_label}."),
        )

    return data


@app.get("/")
async def read_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.post("/api/search", response_model=SearchResponse)
async def search_username(payload: SearchRequest):
    username = payload.username.strip()

    if not username:
        raise HTTPException(status_code=400, detail="الرجاء إدخال اسم مستخدم.")

    if not USERNAME_PATTERN.match(username):
        raise HTTPException(
            status_code=400,
            detail="اسم المستخدم غير صالح. استخدم أحرفًا وأرقامًا و( . _ -) فقط.",
        )

    return await run_subprocess_json(
        SHERLOCK_RUNNER_SCRIPT, [username], SHERLOCK_TIMEOUT_SECONDS, "Sherlock"
    )


@app.post("/api/photon", response_model=PhotonResponse)
async def crawl_url(payload: PhotonRequest):
    url = payload.url.strip()

    if not url:
        raise HTTPException(status_code=400, detail="الرجاء إدخال رابط صالح.")

    if not URL_PATTERN.match(url):
        raise HTTPException(status_code=400, detail="الرابط غير صالح.")

    if not re.match(r"^https?://", url):
        url = f"https://{url}"

    return await run_subprocess_json(
        PHOTON_RUNNER_SCRIPT, [url], PHOTON_TIMEOUT_SECONDS, "Photon"
    )


@app.post("/api/maigret", response_model=MaigretResponse)
async def search_username_maigret(payload: MaigretRequest):
    username = payload.username.strip()

    if not username:
        raise HTTPException(status_code=400, detail="الرجاء إدخال اسم مستخدم.")

    if not USERNAME_PATTERN.match(username):
        raise HTTPException(
            status_code=400,
            detail="اسم المستخدم غير صالح. استخدم أحرفًا وأرقامًا و( . _ -) فقط.",
        )

    return await run_subprocess_json(
        MAIGRET_RUNNER_SCRIPT, [username], MAIGRET_TIMEOUT_SECONDS, "Maigret"
    )


# Mount static files last so that the /api routes above take precedence.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
