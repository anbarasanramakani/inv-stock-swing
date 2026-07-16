"""
data_provider.py
All data acquisition: historical OHLCV, live NSE index levels, live LTP.

Data Sources:
  - yfinance           : Historical EOD daily OHLCV (batch download)
  - NSE India JSON API : Live index values (Nifty 50 / Bank / IT / Midcap) — free
  - nsepython          : Live LTP from NSE quote endpoint — instant, free
"""
import os
import datetime
import time
from pathlib import Path
from typing import Optional

import yfinance as yf
import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Streamlit is optional — used only when running as the Streamlit frontend
try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False

# ---------------------------------------------------------------------------
# NSE request headers (required to avoid 401 from NSE servers)
# ---------------------------------------------------------------------------
_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


_NSE_SESSION_TTL = 300  # seconds — reuse the same TCP session for up to 5 minutes
_nse_session_cache: dict = {"session": None, "ts": 0.0}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, ConnectionError))
)
def _get_nse_session() -> requests.Session:
    """Returns a requests.Session seeded with NSE cookies.

    The session is reused for up to ``_NSE_SESSION_TTL`` seconds to avoid
    creating a new TCP handshake + cookie exchange on every caller. If the
    cached session is expired or absent a fresh one is created.
    """
    now = time.time()
    cached = _nse_session_cache
    if cached["session"] is not None and (now - cached["ts"]) < _NSE_SESSION_TTL:
        return cached["session"]
    session = requests.Session()
    session.headers.update(_NSE_HEADERS)
    session.get("https://www.nseindia.com", timeout=2.5)
    cached["session"] = session
    cached["ts"] = now
    return session


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------
def _flatten_and_clean(df: pd.DataFrame, min_rows: int = 2) -> pd.DataFrame | None:
    """
    Accepts a DataFrame that may have MultiIndex columns (Price, Ticker) or
    flat columns (Price). Flattens to flat columns and returns cleaned df or None.
    """
    if df is None or df.empty:
        return None

    # Flatten MultiIndex — always (Price, Ticker) in yfinance >= 0.2.40
    if isinstance(df.columns, pd.MultiIndex):
        # Use only the first level (Price names: Close, High, Low, Open, Volume)
        df.columns = df.columns.get_level_values(0)

    if 'Close' not in df.columns:
        return None

    # Coerce all price/volume columns to numeric
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.dropna(subset=['Close'])
    return df if len(df) >= min_rows else None


# ---------------------------------------------------------------------------
# Live Index Data — NSE JSON (60-second cache, completely free)
# ---------------------------------------------------------------------------
def _cache_data_decorator(fn):
    """Apply st.cache_data only when running under Streamlit."""
    if _HAS_STREAMLIT:
        return st.cache_data(ttl=60)(fn)
    return fn

@_cache_data_decorator
def get_live_nse_indices() -> list:
    """
    Fetches live index levels from NSE India's allIndices JSON endpoint.
    Returns a list of {name, last, change, pChange} dicts.
    Falls back to empty list on failure.
    """
    WANTED = {"NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY MIDCAP 100", "NIFTY 500"}
    try:
        session = _get_nse_session()
        resp = session.get("https://www.nseindia.com/api/allIndices", timeout=2.5)
        if resp.status_code == 200:
            results = []
            for item in resp.json().get("data", []):
                name = item.get("indexSymbol", "").upper().strip()
                if name in WANTED:
                    results.append({
                        "name":    name,
                        "last":    float(item.get("last", 0)),
                        "change":  float(item.get("change", 0)),
                        "pChange": float(item.get("percentChange", 0)),
                    })
            if results:
                return results
    except Exception as e:
        print(f"[NSE Index API] {e}")
    return []


# ---------------------------------------------------------------------------
# Live LTP — nselib → yfinance 1-min fallback
# ---------------------------------------------------------------------------
@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((requests.RequestException,))
)
def get_live_ltp(symbol: str) -> Optional[float]:
    """
    Returns live Last Traded Price for an NSE symbol (WITHOUT .NS suffix).
    Priority: nselib → yfinance 1-min intraday.
    """
    # 1. nselib (more reliable than nsepython)
    try:
        from nselib import Nse
        nse = Nse()
        quote = nse.get_quote(symbol)
        if quote and 'lastPrice' in quote:
            ltp = float(quote['lastPrice'])
            if ltp > 0:
                return ltp
    except Exception:
        pass

    # 2. yfinance 1-min (works outside market hours too)
    try:
        ticker_sym = f"{symbol}.NS"
        live_df = yf.download(ticker_sym, period="1d", interval="1m",
                               auto_adjust=True, progress=False, threads=False)
        if not live_df.empty:
            df_clean = _flatten_and_clean(live_df, min_rows=1)
            if df_clean is not None:
                return float(df_clean['Close'].dropna().iloc[-1])
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Batch Historical Downloader — yfinance EOD daily (Cache-Backed Incremental)
# ---------------------------------------------------------------------------
_CACHE_DIR = Path(__file__).parent / ".cache"
_CACHE_DIR.mkdir(exist_ok=True)

def _load_cached_ticker(ticker: str) -> pd.DataFrame | None:
    cache_path = os.path.join(_CACHE_DIR, f"{ticker}.csv")
    if os.path.exists(cache_path):
        try:
            # Check 30-day expiration
            file_age_days = (time.time() - os.path.getmtime(cache_path)) / (60 * 60 * 24)
            if file_age_days > 30:
                os.remove(cache_path)
                return None
                
            df = pd.read_csv(cache_path, index_col=0)
            df.index = pd.to_datetime(df.index)
            # Flatten if MultiIndex
            df = _flatten_and_clean(df, min_rows=2)
            return df
        except Exception as e:
            print(f"Error loading cache for {ticker}: {e}")
    return None

def _save_cached_ticker(ticker: str, df: pd.DataFrame):
    if df is not None and not df.empty:
        try:
            cache_path = os.path.join(_CACHE_DIR, f"{ticker}.csv")
            df.to_csv(cache_path)
        except Exception as e:
            print(f"Error saving cache for {ticker}: {e}")


def download_stock_data_batch(tickers: list, period: str = "1y") -> dict:
    """
    Downloads EOD daily OHLCV for a list of tickers, using local incremental caching.
    Aggregates batch downloads for new/out-of-date records to maintain performance.
    """
    if not tickers:
        return {}

    ticker_dfs = {}
    tickers_to_fetch_full = []
    tickers_to_fetch_incremental = {}  # last_date -> list of tickers
    
    # 1. Inspect local caches
    for ticker in tickers:
        df_cached = _load_cached_ticker(ticker)
        if df_cached is not None:
            last_date = df_cached.index.max().date()
            if last_date >= datetime.date.today():
                ticker_dfs[ticker] = df_cached
            else:
                last_date_str = last_date.strftime("%Y-%m-%d")
                if last_date_str not in tickers_to_fetch_incremental:
                    tickers_to_fetch_incremental[last_date_str] = []
                tickers_to_fetch_incremental[last_date_str].append(ticker)
        else:
            tickers_to_fetch_full.append(ticker)
            
    # 2. Fetch full downloads for tickers with no caches
    if tickers_to_fetch_full:
        try:
            print(f"Downloading full history for {len(tickers_to_fetch_full)} tickers...")
            data_full = yf.download(tickers=tickers_to_fetch_full, period=period, auto_adjust=True, progress=False, threads=False)
            if not data_full.empty:
                if isinstance(data_full.columns, pd.MultiIndex):
                    avail = data_full.columns.get_level_values(1).unique().tolist()
                    for t in tickers_to_fetch_full:
                        if t in avail:
                            df = data_full.xs(t, axis=1, level=1).copy()
                            df_clean = _flatten_and_clean(df, min_rows=2)
                            if df_clean is not None:
                                ticker_dfs[t] = df_clean
                                _save_cached_ticker(t, df_clean)
                else:
                    if len(tickers_to_fetch_full) == 1:
                        df_clean = _flatten_and_clean(data_full, min_rows=2)
                        if df_clean is not None:
                            ticker_dfs[tickers_to_fetch_full[0]] = df_clean
                            _save_cached_ticker(tickers_to_fetch_full[0], df_clean)
        except Exception as e:
            print(f"Batch full download error: {e}")

    # 3. Fetch incremental downloads group by last_date
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    for start_date, inc_tickers in tickers_to_fetch_incremental.items():
        try:
            print(f"Downloading incremental data ({start_date} to today) for {len(inc_tickers)} tickers...")
            data_inc = yf.download(tickers=inc_tickers, start=start_date, end=tomorrow, auto_adjust=True, progress=False, threads=False)
            if not data_inc.empty:
                if isinstance(data_inc.columns, pd.MultiIndex):
                    avail = data_inc.columns.get_level_values(1).unique().tolist()
                    for t in inc_tickers:
                        df_cached = _load_cached_ticker(t)
                        if t in avail:
                            df_new = data_inc.xs(t, axis=1, level=1).copy()
                            df_new_clean = _flatten_and_clean(df_new, min_rows=1)
                            if df_new_clean is not None and not df_new_clean.empty:
                                df_combined = pd.concat([df_cached, df_new_clean])
                                df_combined = df_combined[~df_combined.index.duplicated(keep='last')]
                                df_combined = df_combined.sort_index()
                                ticker_dfs[t] = df_combined
                                _save_cached_ticker(t, df_combined)
                            else:
                                ticker_dfs[t] = df_cached
                        else:
                            ticker_dfs[t] = df_cached
                else:
                    if len(inc_tickers) == 1:
                        t = inc_tickers[0]
                        df_cached = _load_cached_ticker(t)
                        df_new_clean = _flatten_and_clean(data_inc, min_rows=1)
                        if df_new_clean is not None and not df_new_clean.empty:
                            df_combined = pd.concat([df_cached, df_new_clean])
                            df_combined = df_combined[~df_combined.index.duplicated(keep='last')]
                            df_combined = df_combined.sort_index()
                            ticker_dfs[t] = df_combined
                            _save_cached_ticker(t, df_combined)
                        else:
                            ticker_dfs[t] = df_cached
        except Exception as e:
            print(f"Incremental batch download failed for {start_date}: {e}")
            for t in inc_tickers:
                df_cached = _load_cached_ticker(t)
                if df_cached is not None:
                    ticker_dfs[t] = df_cached

    return ticker_dfs


def get_single_stock_data(ticker: str, period: str = "1y") -> pd.DataFrame | None:
    """Fetch EOD data for a single stock, using local incremental caching."""
    df_cached = _load_cached_ticker(ticker)
    if df_cached is not None:
        last_date = df_cached.index.max()
        if last_date.date() >= datetime.date.today():
            return df_cached
            
        try:
            start_date = last_date.strftime("%Y-%m-%d")
            tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            data_new = yf.download(ticker, start=start_date, end=tomorrow, auto_adjust=True, progress=False, threads=False)
            df_new = _flatten_and_clean(data_new, min_rows=1)
            
            if df_new is not None and not df_new.empty:
                df_combined = pd.concat([df_cached, df_new])
                df_combined = df_combined[~df_combined.index.duplicated(keep='last')]
                df_combined = df_combined.sort_index()
                _save_cached_ticker(ticker, df_combined)
                return df_combined
            return df_cached
        except Exception as e:
            print(f"Incremental download failed for {ticker}, returning cache: {e}")
            return df_cached
            
    try:
        data = yf.download(ticker, period=period, auto_adjust=True, progress=False, threads=False)
        df_fresh = _flatten_and_clean(data, min_rows=2)
        if df_fresh is not None:
            _save_cached_ticker(ticker, df_fresh)
        return df_fresh
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
    return None
