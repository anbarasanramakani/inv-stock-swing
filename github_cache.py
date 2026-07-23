"""
github_cache.py
Permanent cache storage via GitHub Contents API.

Reads/writes JSON files in the GitHub repository so data survives
ALL Streamlit Cloud restarts and redeploys — because the data lives
in git history, not on the ephemeral container filesystem.

Setup (one-time, in Streamlit Cloud Secrets):
  GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"
  GITHUB_REPO  = "anbarasanramakani/inv-stock-swing"

Create token at: https://github.com/settings/tokens/new
  -> Fine-grained token -> Repository: inv-stock-swing
  -> Permissions: Contents -> Read and Write
"""
import json
import base64
import datetime
import threading
import time
import os
from typing import Any, Optional

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_API_BASE = "https://api.github.com"

# Background write queue: { filepath -> data }
_WRITE_QUEUE: dict = {}
_QUEUE_LOCK = threading.Lock()

# Rate-limit: track last successful write time per file
_LAST_WRITE: dict = {}
_WRITE_INTERVAL = 300   # 5 minutes minimum between writes to the same file

# SHA cache: avoids extra GET calls when we know the file's current SHA
_FILE_SHA: dict = {}

_WRITE_THREAD: Optional[threading.Thread] = None
_INIT_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _get_config():
    """Return (token, repo) from Streamlit secrets or environment variables."""
    token = None
    repo = None

    if _HAS_STREAMLIT:
        try:
            token = st.secrets.get("GITHUB_TOKEN")
            repo  = st.secrets.get("GITHUB_REPO")
        except Exception:
            pass

    # Fallback: environment variables (for local dev)
    if not token:
        token = os.environ.get("GITHUB_TOKEN")
    if not repo:
        repo = os.environ.get("GITHUB_REPO", "")

    return token, repo


def is_available() -> bool:
    """Return True if GitHub cache is configured and requests is available."""
    token, repo = _get_config()
    return bool(token and repo and _HAS_REQUESTS)


def _headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Core API operations
# ---------------------------------------------------------------------------

def github_read_json(filepath: str) -> Optional[Any]:
    """
    Read a JSON file from the GitHub repository.

    Args:
        filepath: relative path in repo (e.g., "news_cache.json")

    Returns:
        Parsed Python object, or None on any failure.
    """
    if not _HAS_REQUESTS:
        return None

    token, repo = _get_config()
    if not token or not repo:
        return None

    try:
        url  = f"{_API_BASE}/repos/{repo}/contents/{filepath}"
        resp = _requests.get(url, headers=_headers(token), timeout=12)

        if resp.status_code == 200:
            payload   = resp.json()
            sha       = payload.get("sha", "")
            # Cache SHA so subsequent writes can skip the extra GET
            _FILE_SHA[filepath] = sha
            b64_raw   = payload.get("content", "")
            raw_bytes = base64.b64decode(b64_raw.replace("\n", ""))
            return json.loads(raw_bytes.decode("utf-8"))

        elif resp.status_code == 404:
            return None   # File doesn't exist yet
        else:
            print(f"[GH Cache] Read failed {filepath}: HTTP {resp.status_code}")
            return None

    except Exception as exc:
        print(f"[GH Cache] Read error {filepath}: {exc}")
        return None


def github_write_json(filepath: str, data: Any,
                      commit_message: Optional[str] = None) -> bool:
    """
    Create or update a JSON file in the GitHub repository.

    Args:
        filepath:       relative path in repo (e.g., "news_cache.json")
        data:           JSON-serializable Python object
        commit_message: optional commit message (auto-generated if None)

    Returns:
        True on success, False on failure.
    """
    if not _HAS_REQUESTS:
        return False

    token, repo = _get_config()
    if not token or not repo:
        return False

    try:
        url  = f"{_API_BASE}/repos/{repo}/contents/{filepath}"
        hdrs = _headers(token)

        # Get current SHA (needed for updates).
        # Use cached SHA if available, else do a fresh GET.
        sha = _FILE_SHA.get(filepath)
        if not sha:
            get_resp = _requests.get(url, headers=hdrs, timeout=10)
            if get_resp.status_code == 200:
                sha = get_resp.json().get("sha")
                _FILE_SHA[filepath] = sha

        # Encode content as base64
        content_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("ascii")

        if commit_message is None:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M IST")
            commit_message = f"chore: auto-cache {filepath} [{ts}]"

        body: dict = {"message": commit_message, "content": content_b64}
        if sha:
            body["sha"] = sha

        put_resp = _requests.put(url, headers=hdrs, json=body, timeout=20)

        if put_resp.status_code in (200, 201):
            # Update the cached SHA for the next write
            try:
                new_sha = put_resp.json().get("content", {}).get("sha")
                if new_sha:
                    _FILE_SHA[filepath] = new_sha
            except Exception:
                pass
            return True

        # 409 Conflict -> SHA mismatch -> clear cached SHA and retry once
        if put_resp.status_code == 409:
            _FILE_SHA.pop(filepath, None)
            print(f"[GH Cache] SHA conflict on {filepath}, retrying...")
            return github_write_json(filepath, data, commit_message)

        print(f"[GH Cache] Write failed {filepath}: HTTP {put_resp.status_code}")
        return False

    except Exception as exc:
        print(f"[GH Cache] Write error {filepath}: {exc}")
        return False


# ---------------------------------------------------------------------------
# Async background writer
# ---------------------------------------------------------------------------

def _bg_flush_worker():
    """
    Background daemon thread that flushes queued writes to GitHub.
    Runs every 45 seconds; respects per-file rate limits (5 min).
    """
    while True:
        time.sleep(45)
        try:
            with _QUEUE_LOCK:
                items = dict(_WRITE_QUEUE)
                _WRITE_QUEUE.clear()

            requeue = {}
            for filepath, payload in items.items():
                now  = time.time()
                last = _LAST_WRITE.get(filepath, 0)
                if now - last >= _WRITE_INTERVAL:
                    ok = github_write_json(filepath, payload)
                    if ok:
                        _LAST_WRITE[filepath] = now
                        print(f"[GH Cache] Persisted {filepath} to GitHub")
                    else:
                        requeue[filepath] = payload   # retry next cycle
                else:
                    requeue[filepath] = payload       # too soon, defer

            if requeue:
                with _QUEUE_LOCK:
                    for k, v in requeue.items():
                        if k not in _WRITE_QUEUE:
                            _WRITE_QUEUE[k] = v

        except Exception as exc:
            print(f"[GH Cache] Flush thread error: {exc}")


def _ensure_bg_writer():
    """Start the background writer thread (idempotent)."""
    global _WRITE_THREAD
    with _INIT_LOCK:
        if _WRITE_THREAD is None or not _WRITE_THREAD.is_alive():
            _WRITE_THREAD = threading.Thread(
                target=_bg_flush_worker,
                daemon=True,
                name="gh-cache-writer",
            )
            _WRITE_THREAD.start()


def queue_write(filepath: str, data: Any):
    """
    Non-blocking: queue a write to GitHub (flushed in background every 45s).

    Usage:
        github_cache.queue_write("news_cache.json", news_list)
    """
    _ensure_bg_writer()
    with _QUEUE_LOCK:
        _WRITE_QUEUE[filepath] = data


def flush_now(filepath: str, data: Any) -> bool:
    """
    Blocking: write immediately to GitHub (bypasses the queue).
    Use when you need guaranteed persistence before app exits.
    """
    return github_write_json(filepath, data)
