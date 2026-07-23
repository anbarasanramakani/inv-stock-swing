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

# ---------------------------------------------------------------------------
# Diagnostics & Status
# ---------------------------------------------------------------------------
_LAST_ERROR: str = ""
_LAST_STATUS: str = "Not initialized"
_CACHED_TOKEN: Optional[str] = None
_CACHED_REPO: Optional[str] = None


def get_last_status() -> tuple[str, str]:
    """Return (status_summary, last_error_message)."""
    return _LAST_STATUS, _LAST_ERROR


def _get_config():
    """Return (token, repo) from Streamlit secrets or environment variables."""
    global _CACHED_TOKEN, _CACHED_REPO
    if _CACHED_TOKEN and _CACHED_REPO:
        return _CACHED_TOKEN, _CACHED_REPO

    token = None
    repo = None

    if _HAS_STREAMLIT:
        try:
            # Check various common secret keys
            token = (
                st.secrets.get("GITHUB_TOKEN") or
                st.secrets.get("github_token") or
                st.secrets.get("GITHUB", {}).get("TOKEN") or
                st.secrets.get("github", {}).get("token")
            )
            repo = (
                st.secrets.get("GITHUB_REPO") or
                st.secrets.get("github_repo") or
                st.secrets.get("GITHUB", {}).get("REPO") or
                st.secrets.get("github", {}).get("repo")
            )
        except Exception:
            pass

    # Fallback: environment variables (for local dev)
    if not token:
        token = os.environ.get("GITHUB_TOKEN")
    if not repo:
        repo = os.environ.get("GITHUB_REPO", "")

    # Clean token & repo strings if present
    if token:
        token = str(token).strip().strip("'").strip('"')
    if repo:
        repo = str(repo).strip().strip("'").strip('"')
    else:
        # Default to this repository if not specified
        repo = "anbarasanramakani/inv-stock-swing"

    if token and repo:
        _CACHED_TOKEN = token
        _CACHED_REPO = repo

    return token, repo


def is_available() -> bool:
    """Return True if GitHub cache is configured and requests is available."""
    token, repo = _get_config()
    return bool(token and repo and _HAS_REQUESTS)


def _headers(token: str) -> dict:
    # Use Bearer token authorization format (works for both ghp_ and github_pat_ tokens)
    auth_val = f"Bearer {token}" if not token.startswith("token ") else token
    return {
        "Authorization": auth_val,
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Core API operations
# ---------------------------------------------------------------------------

def github_read_json(filepath: str) -> Optional[Any]:
    """
    Read a JSON file from the GitHub repository.
    """
    global _LAST_ERROR, _LAST_STATUS

    if not _HAS_REQUESTS:
        _LAST_ERROR = "requests library missing"
        return None

    token, repo = _get_config()
    if not token or not repo:
        _LAST_ERROR = "GITHUB_TOKEN missing in Streamlit secrets"
        _LAST_STATUS = "Missing GITHUB_TOKEN"
        return None

    try:
        url  = f"{_API_BASE}/repos/{repo}/contents/{filepath}"
        resp = _requests.get(url, headers=_headers(token), timeout=12)

        if resp.status_code == 200:
            payload   = resp.json()
            sha       = payload.get("sha", "")
            _FILE_SHA[filepath] = sha
            b64_raw   = payload.get("content", "")
            raw_bytes = base64.b64decode(b64_raw.replace("\n", ""))
            _LAST_STATUS = "Connected & Active"
            _LAST_ERROR = ""
            return json.loads(raw_bytes.decode("utf-8"))

        elif resp.status_code == 404:
            _LAST_STATUS = f"File {filepath} not found"
            return None   # File doesn't exist yet
        else:
            _LAST_ERROR = f"Read failed HTTP {resp.status_code}: {resp.text[:100]}"
            _LAST_STATUS = f"HTTP {resp.status_code} Error"
            print(f"[GH Cache] Read failed {filepath}: HTTP {resp.status_code}")
            return None

    except Exception as exc:
        _LAST_ERROR = f"Read Exception: {exc}"
        _LAST_STATUS = "Network Error"
        print(f"[GH Cache] Read error {filepath}: {exc}")
        return None


def github_write_json(filepath: str, data: Any,
                      commit_message: Optional[str] = None) -> bool:
    """
    Create or update a JSON file in the GitHub repository.
    """
    global _LAST_ERROR, _LAST_STATUS

    if not _HAS_REQUESTS:
        _LAST_ERROR = "requests library missing"
        return False

    token, repo = _get_config()
    if not token or not repo:
        _LAST_ERROR = "GITHUB_TOKEN missing in Streamlit secrets"
        _LAST_STATUS = "Missing GITHUB_TOKEN"
        return False

    try:
        url  = f"{_API_BASE}/repos/{repo}/contents/{filepath}"
        hdrs = _headers(token)

        # Get current SHA (needed for updates)
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
            try:
                new_sha = put_resp.json().get("content", {}).get("sha")
                if new_sha:
                    _FILE_SHA[filepath] = new_sha
            except Exception:
                pass
            _LAST_STATUS = "Write Successful"
            _LAST_ERROR = ""
            return True

        # 409 Conflict -> SHA mismatch -> clear cached SHA and retry once
        if put_resp.status_code == 409:
            _FILE_SHA.pop(filepath, None)
            print(f"[GH Cache] SHA conflict on {filepath}, retrying...")
            return github_write_json(filepath, data, commit_message)

        _LAST_ERROR = f"Write failed HTTP {put_resp.status_code}: {put_resp.text[:100]}"
        _LAST_STATUS = f"HTTP {put_resp.status_code} Write Error"
        print(f"[GH Cache] Write failed {filepath}: HTTP {put_resp.status_code}")
        return False

    except Exception as exc:
        _LAST_ERROR = f"Write Exception: {exc}"
        _LAST_STATUS = "Network Error"
        print(f"[GH Cache] Write error {filepath}: {exc}")
        return False


# ---------------------------------------------------------------------------
# Async background writer
# ---------------------------------------------------------------------------
_GH_WRITE_LOCK = threading.Lock()

def _immediate_bg_write(filepath: str, data: Any):
    """Worker function that runs in an isolated thread but writes immediately."""
    try:
        with _GH_WRITE_LOCK:
            ok = github_write_json(filepath, data)
            if ok:
                _LAST_WRITE[filepath] = time.time()
                print(f"[GH Cache] ✅ Persisted {filepath} to GitHub")
    except Exception as exc:
        print(f"[GH Cache] Flush thread error: {exc}")


def queue_write(filepath: str, data: Any):
    """
    Queue a write to GitHub (flushed in background immediately).
    Uses a Lock to prevent 409 SHA collisions on concurrent updates.
    """
    t = threading.Thread(
        target=_immediate_bg_write,
        args=(filepath, data),
        daemon=True,
        name=f"gh-writer-{filepath}"
    )
    
    # Try to attach Streamlit context so the thread isn't killed
    if _HAS_STREAMLIT:
        try:
            from streamlit.runtime.scriptrunner import add_script_run_ctx
            add_script_run_ctx(t)
        except Exception:
            pass

    t.start()


def flush_now(filepath: str, data: Any) -> bool:
    """
    Blocking: write immediately to GitHub (bypasses the queue).
    """
    with _GH_WRITE_LOCK:
        return github_write_json(filepath, data)

