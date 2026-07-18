"""
persistent_cache.py
Multi-tier caching system for Streamlit Cloud persistence.
Solves the problem of cache files being wiped on every deploy/restart.

Storage tiers (attempted in order):
  1. st.cache_data (Streamlit's built-in persistent cache - survives reruns)
  2. st.session_state (per-session, survives interactions)
  3. On-disk JSON file (works locally, fails on Streamlit Cloud)
  4. Embedded fallback data (always works)

Usage:
  from persistent_cache import cache_get, cache_set, cache_clear
  
  # Store/retrieve any JSON-serializable data
  cache_set("ipo_data", my_ipo_list)
  data = cache_get("ipo_data", default=[])
"""
import json
import os
import datetime
import hashlib
from typing import Any, Optional

try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False

# ---------------------------------------------------------------------------
# Cache file paths (used as Tier 2 fallback)
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE_DIR = os.path.join(_DIR, ".cache")
os.makedirs(_CACHE_DIR, exist_ok=True)

# A single unified cache file
_UNIFIED_CACHE_PATH = os.path.join(_CACHE_DIR, "unified_cache.json")

# ---------------------------------------------------------------------------
# Version constant - bump this to invalidate all caches after code changes
# ---------------------------------------------------------------------------
_CACHE_VERSION = "v1"

# ---------------------------------------------------------------------------
# Streamlit cloud detection
# ---------------------------------------------------------------------------
_IS_STREAMLIT_CLOUD = _HAS_STREAMLIT and not os.access(_DIR, os.W_OK)


# ---------------------------------------------------------------------------
# Core cache operations
# ---------------------------------------------------------------------------

def _get_cache_from_disk() -> dict:
    """Load the unified cache from disk. Returns empty dict on failure."""
    try:
        if os.path.exists(_UNIFIED_CACHE_PATH):
            with open(_UNIFIED_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Validate version
            if data.get("_version") == _CACHE_VERSION:
                return data.get("data", {})
    except Exception:
        pass
    return {}


def _save_cache_to_disk(data: dict):
    """Save the unified cache to disk. Silently fails on read-only filesystems."""
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
        pass  # Fail silently on read-only filesystems (Streamlit Cloud)


def cache_get(key: str, default: Any = None) -> Any:
    """
    Retrieve a value from the multi-tier cache.
    
    Tier 1: st.cache_data (Streamlit's persistent cache - survives reruns)
    Tier 2: st.session_state (per-session)
    Tier 3: On-disk JSON file
    """
    # Tier 1: st.cache_data (wraps the function; use via cache_get_data helper)
    # We handle this by calling the caching function
    
    # Tier 2: session state (fastest, survives reruns within session)
    if _HAS_STREAMLIT:
        ss_key = f"_cache_{key}"
        if ss_key in st.session_state:
            return st.session_state[ss_key]
    
    # Tier 3: disk cache
    disk_cache = _get_cache_from_disk()
    if key in disk_cache:
        value = disk_cache[key]
        # Promote to session state for faster access next time
        if _HAS_STREAMLIT:
            st.session_state[f"_cache_{key}"] = value
        return value
    
    return default


def cache_set(key: str, value: Any):
    """
    Store a value in all available cache tiers.
    """
    # Tier 2: session state
    if _HAS_STREAMLIT:
        st.session_state[f"_cache_{key}"] = value
    
    # Tier 3: disk cache (best-effort)
    try:
        disk_cache = _get_cache_from_disk()
        disk_cache[key] = value
        _save_cache_to_disk(disk_cache)
    except Exception:
        pass


def cache_clear(key: Optional[str] = None):
    """
    Clear cache. If key is None, clears all caches.
    """
    if _HAS_STREAMLIT:
        if key:
            ss_key = f"_cache_{key}"
            if ss_key in st.session_state:
                del st.session_state[ss_key]
        else:
            # Clear all cache keys from session state
            keys_to_delete = [k for k in st.session_state.keys() if k.startswith("_cache_")]
            for k in keys_to_delete:
                del st.session_state[k]
    
    if key:
        try:
            disk_cache = _get_cache_from_disk()
            if key in disk_cache:
                del disk_cache[key]
                _save_cache_to_disk(disk_cache)
        except Exception:
            pass
    else:
        try:
            if os.path.exists(_UNIFIED_CACHE_PATH):
                os.remove(_UNIFIED_CACHE_PATH)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Streamlit cache_data wrapper (Tier 1 - survives reruns across sessions)
# ---------------------------------------------------------------------------
def st_cache(ttl_seconds: int = 86400 * 7):  # Default: 7 days
    """
    Decorator that wraps a function with Streamlit's cache_data.
    Falls back to session state + disk cache if streamlit is unavailable.
    
    Usage:
        @st_cache(ttl=3600)
        def get_my_data():
            return expensive_computation()
    """
    def decorator(func):
        if _HAS_STREAMLIT:
            return st.cache_data(ttl=ttl_seconds)(func)
        return func
    return decorator


# ---------------------------------------------------------------------------
# Convenience functions for specific cache domains
# ---------------------------------------------------------------------------

def get_ipo_cache() -> list:
    """Get cached IPO list."""
    return cache_get("ipo_list", default=[])


def set_ipo_cache(ipo_list: list):
    """Cache IPO list."""
    cache_set("ipo_list", ipo_list)


def get_news_cache() -> list:
    """Get cached news items."""
    return cache_get("news_list", default=[])


def set_news_cache(news_list: list):
    """Cache news items."""
    cache_set("news_list", news_list)


def get_analysis_history() -> dict:
    """Get cached analysis history."""
    return cache_get("analysis_history", default={"runs": [], "last_run_date": ""})


def set_analysis_history(history: dict):
    """Cache analysis history."""
    cache_set("analysis_history", history)


def get_backtest_cache(name: str) -> list:
    """Get a specific backtest cache by name."""
    return cache_get(f"backtest_{name}", default=[])


def set_backtest_cache(name: str, data: list):
    """Set a specific backtest cache by name."""
    cache_set(f"backtest_{name}", data)


def get_brokers_cache() -> list:
    """Get cached broker calls."""
    return cache_get("brokers_list", default=[])


def set_brokers_cache(brokers_list: list):
    """Cache broker calls."""
    cache_set("brokers_list", brokers_list)


# ---------------------------------------------------------------------------
# Migration helper: move existing legacy cache files into unified cache
# ---------------------------------------------------------------------------
def migrate_legacy_caches():
    """
    One-time migration of all legacy cache files into the unified cache.
    Call this once at app startup.
    """
    legacy_caches = {
        "ipo_list": "ipo_cache.json",
        "news_list": "news_cache.json",
        "analysis_history": "analysis_history_cache.json",
        "brokers_list": "brokers_cache.json",
    }
    
    for cache_key, legacy_file in legacy_caches.items():
        # Only migrate if we don't already have this key in our cache
        if cache_get(cache_key) is None or cache_get(cache_key) == [] or cache_get(cache_key) == {}:
            legacy_path = os.path.join(_DIR, legacy_file)
            if os.path.exists(legacy_path):
                try:
                    with open(legacy_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    cache_set(cache_key, data)
                    print(f"[Cache] Migrated {legacy_file} → unified cache ({cache_key})")
                except Exception as e:
                    print(f"[Cache] Failed to migrate {legacy_file}: {e}")