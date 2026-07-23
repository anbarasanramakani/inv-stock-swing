"""
persistent_cache.py
Multi-tier caching system for Streamlit Cloud permanent persistence.

Storage tiers (attempted in order on READ):
  1. st.session_state      -- fastest; per browser session
  2. GitHub API            -- permanent across all restarts/redeploys
  3. Local disk JSON file  -- instant; works locally, wiped on Cloud restart
  4. Seed JSON files       -- git-tracked fallback; always available on cold start

On WRITE all tiers are updated:
  1. st.session_state      -- immediate
  2. Local disk JSON file  -- immediate (local dev / same-session)
  3. GitHub API (async)    -- background thread; 5 min rate limit per file

Usage:
  from persistent_cache import cache_get, cache_set
  cache_set("news_list", my_news_items)
  data = cache_get("news_list", default=[])
"""
import json
import os
import datetime
from typing import Any, Optional

try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False

# Import GitHub cache backend (graceful fallback if unavailable)
try:
    import github_cache as _gh
    _HAS_GH = True
except ImportError:
    _gh = None
    _HAS_GH = False

# ---------------------------------------------------------------------------
# Disk cache paths
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE_DIR = os.path.join(_DIR, ".cache")
os.makedirs(_CACHE_DIR, exist_ok=True)
_UNIFIED_CACHE_PATH = os.path.join(_CACHE_DIR, "unified_cache.json")

_CACHE_VERSION = "v2"   # bump to invalidate old caches

# ---------------------------------------------------------------------------
# Mapping: cache key -> filename in the repo
# These files are git-tracked and used as seed data on cold start.
# The GitHub API writes back to these same files so they stay up-to-date.
# ---------------------------------------------------------------------------
_GITHUB_MAP = {
    "ipo_list":          "ipo_cache.json",
    "news_list":         "news_cache.json",
    "analysis_history":  "analysis_history_cache.json",
    "brokers_list":      "brokers_cache.json",
}

# Track which keys have already been loaded from GitHub this session
# (prevents repeated API calls on every cache_get)
_GITHUB_LOADED: set = set()


# ---------------------------------------------------------------------------
# Disk helpers
# ---------------------------------------------------------------------------

def _read_disk_cache() -> dict:
    try:
        if os.path.exists(_UNIFIED_CACHE_PATH):
            with open(_UNIFIED_CACHE_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if raw.get("_version") == _CACHE_VERSION:
                return raw.get("data", {})
    except Exception:
        pass
    return {}


def _write_disk_cache(data: dict):
    try:
        os.makedirs(os.path.dirname(_UNIFIED_CACHE_PATH), exist_ok=True)
        payload = {
            "_version": _CACHE_VERSION,
            "_updated": datetime.datetime.now().isoformat(),
            "data": data,
        }
        with open(_UNIFIED_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception:
        pass  # Read-only filesystem on Streamlit Cloud is expected


def _read_seed_file(key: str) -> Any:
    """Read from the git-tracked seed JSON file for this key."""
    if key not in _GITHUB_MAP:
        return None
    path = os.path.join(_DIR, _GITHUB_MAP[key])
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if data else None
    except Exception:
        return None


def _write_seed_file(key: str, value: Any):
    """Write to the git-tracked seed JSON file (best-effort)."""
    if key not in _GITHUB_MAP:
        return
    path = os.path.join(_DIR, _GITHUB_MAP[key])
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, ensure_ascii=False, default=str)
    except Exception:
        pass


def _is_empty(val: Any) -> bool:
    """Return True when a cached value should be treated as absent."""
    if val is None:
        return True
    if isinstance(val, (list, dict)) and len(val) == 0:
        return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def cache_get(key: str, default: Any = None) -> Any:
    """
    Retrieve a value from the multi-tier persistent cache.

    Read order:
      1. st.session_state  (per-session, instant)
      2. GitHub API        (permanent, ~200 ms, fetched once per key per session)
      3. Local disk        (ephemeral, but fast)
      4. Seed JSON file    (git-tracked, always available)
    """
    # ── Tier 1: session state ──────────────────────────────────────────────
    if _HAS_STREAMLIT:
        ss_key = f"_cache_{key}"
        val = st.session_state.get(ss_key)
        if not _is_empty(val):
            return val

    # ── Tier 2: GitHub API (fetched once per key per session) ─────────────
    if key not in _GITHUB_LOADED and key in _GITHUB_MAP:
        if _HAS_GH and _gh.is_available():
            filepath = _GITHUB_MAP[key]
            try:
                gh_val = _gh.github_read_json(filepath)
                if not _is_empty(gh_val):
                    _GITHUB_LOADED.add(key)  # Mark loaded only when gh_val is valid!
                    print(f"[Cache] Loaded '{key}' from GitHub ({filepath})")
                    # Populate lower tiers so subsequent reads are instant
                    if _HAS_STREAMLIT:
                        st.session_state[f"_cache_{key}"] = gh_val
                    try:
                        dc = _read_disk_cache()
                        dc[key] = gh_val
                        _write_disk_cache(dc)
                    except Exception:
                        pass
                    _write_seed_file(key, gh_val)
                    return gh_val
            except Exception as exc:
                print(f"[Cache] GitHub read error for '{key}': {exc}")

    # ── Tier 3: local disk unified cache ──────────────────────────────────
    try:
        dc  = _read_disk_cache()
        val = dc.get(key)
        if not _is_empty(val):
            if _HAS_STREAMLIT:
                st.session_state[f"_cache_{key}"] = val
            return val
    except Exception:
        pass

    # ── Tier 4: git-tracked seed file ─────────────────────────────────────
    seed = _read_seed_file(key)
    if not _is_empty(seed):
        if _HAS_STREAMLIT:
            st.session_state[f"_cache_{key}"] = seed
        # Promote to disk for faster access next time
        try:
            dc = _read_disk_cache()
            dc[key] = seed
            _write_disk_cache(dc)
        except Exception:
            pass
        return seed

    return default


def cache_set(key: str, value: Any):
    """
    Store a value in all cache tiers.

    Write order (all executed):
      1. st.session_state  -- immediate
      2. Local disk        -- immediate (works locally; wiped on Cloud restart)
      3. Seed JSON file    -- immediate local write
      4. GitHub API        -- queued & immediate async write to GitHub
    """
    import threading

    # ── Tier 1: session state ──────────────────────────────────────────────
    if _HAS_STREAMLIT:
        st.session_state[f"_cache_{key}"] = value

    # ── Tier 2: local disk unified cache ──────────────────────────────────
    try:
        dc = _read_disk_cache()
        dc[key] = value
        _write_disk_cache(dc)
    except Exception:
        pass

    # ── Tier 3: seed JSON file (git-tracked) ──────────────────────────────
    _write_seed_file(key, value)

    # ── Tier 4: GitHub API (async, non-blocking) ──────────────────────────
    if _HAS_GH and _gh.is_available() and key in _GITHUB_MAP:
        try:
            _gh.queue_write(_GITHUB_MAP[key], value)
            # Immediate non-blocking background flush to GitHub
            threading.Thread(
                target=_gh.flush_now,
                args=(_GITHUB_MAP[key], value),
                daemon=True,
            ).start()
        except Exception as exc:
            print(f"[Cache] GitHub write error for '{key}': {exc}")



def cache_clear(key: Optional[str] = None):
    """Clear cache for a specific key or all keys."""
    if _HAS_STREAMLIT:
        if key:
            ss_key = f"_cache_{key}"
            if ss_key in st.session_state:
                del st.session_state[ss_key]
        else:
            for k in [k for k in st.session_state if k.startswith("_cache_")]:
                del st.session_state[k]

    if key:
        try:
            dc = _read_disk_cache()
            dc.pop(key, None)
            _write_disk_cache(dc)
        except Exception:
            pass
        # Remove from "loaded" tracker so next get re-fetches
        _GITHUB_LOADED.discard(key)
    else:
        try:
            if os.path.exists(_UNIFIED_CACHE_PATH):
                os.remove(_UNIFIED_CACHE_PATH)
        except Exception:
            pass
        _GITHUB_LOADED.clear()


# ---------------------------------------------------------------------------
# Streamlit cache_data decorator wrapper (for function-level caching)
# ---------------------------------------------------------------------------

def st_cache(ttl_seconds: int = 86400 * 30):
    """
    Decorator: wrap a function with Streamlit's cache_data.
    Falls back gracefully on older Streamlit versions.
    """
    def decorator(func):
        if _HAS_STREAMLIT:
            try:
                return st.cache_data(ttl=ttl_seconds, show_spinner=False,
                                     persist="disk")(func)
            except TypeError:
                return st.cache_data(ttl=ttl_seconds, show_spinner=False)(func)
        return func
    return decorator


# ---------------------------------------------------------------------------
# Convenience helpers for each data domain
# ---------------------------------------------------------------------------

def get_ipo_cache() -> list:
    return cache_get("ipo_list", default=[])

def set_ipo_cache(ipo_list: list):
    cache_set("ipo_list", ipo_list)


def get_news_cache() -> list:
    return cache_get("news_list", default=[])

def set_news_cache(news_list: list):
    cache_set("news_list", news_list)


def get_analysis_history() -> dict:
    return cache_get("analysis_history", default={"runs": [], "last_run_date": ""})

def set_analysis_history(history: dict):
    cache_set("analysis_history", history)


def get_backtest_cache(name: str) -> list:
    return cache_get(f"backtest_{name}", default=[])

def set_backtest_cache(name: str, data: list):
    cache_set(f"backtest_{name}", data)


def get_brokers_cache() -> list:
    return cache_get("brokers_list", default=[])

def set_brokers_cache(brokers_list: list):
    cache_set("brokers_list", brokers_list)


# ---------------------------------------------------------------------------
# Startup migration: seed local disk from the git-tracked JSON files
# ---------------------------------------------------------------------------

def migrate_legacy_caches():
    """
    On cold start: if a cache key has no data yet, load it from the
    git-tracked seed file and promote it so subsequent reads are instant.
    Called once at app startup from app.py.
    """
    for key in _GITHUB_MAP:
        # Skip if already in session state
        if _HAS_STREAMLIT:
            if not _is_empty(st.session_state.get(f"_cache_{key}")):
                continue

        # Skip if already in disk cache
        try:
            dc  = _read_disk_cache()
            val = dc.get(key)
            if not _is_empty(val):
                continue
        except Exception:
            pass

        # Try seed file
        seed = _read_seed_file(key)
        if not _is_empty(seed):
            if _HAS_STREAMLIT:
                st.session_state[f"_cache_{key}"] = seed
            try:
                dc = _read_disk_cache()
                dc[key] = seed
                _write_disk_cache(dc)
            except Exception:
                pass
            print(f"[Cache] Seeded '{key}' from {_GITHUB_MAP[key]}")


def status() -> dict:
    """Return diagnostic info about the cache configuration."""
    gh_avail = _HAS_GH and _gh.is_available() if _HAS_GH else False
    return {
        "github_available": gh_avail,
        "session_state_keys": [
            k for k in (st.session_state.keys() if _HAS_STREAMLIT else [])
            if k.startswith("_cache_")
        ],
        "github_loaded_keys": list(_GITHUB_LOADED),
        "disk_cache_exists":  os.path.exists(_UNIFIED_CACHE_PATH),
    }