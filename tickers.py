"""
tickers.py
Manages ticker lists for different NSE universes.

Universes:
  - Nifty 50   : Top 50 large-cap stocks (current as of 2026)
  - Nifty 100  : Top 100 (Nifty 50 + Next 50)
  - Nifty 500  : Downloaded dynamically from NSE archives
  - Nifty 1000 : Nifty 500 + liquid EQ series stocks from EQUITY_L.csv
  - F&O        : ~220 F&O-eligible stocks (most liquid, best for intraday)
"""
from pathlib import Path
from typing import Optional
import pandas as pd
import requests
from io import StringIO
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ---------------------------------------------------------------------------
# Current Nifty 50 constituents (verified July 2026)
# ---------------------------------------------------------------------------
NIFTY50_SYMBOLS = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL",
    "BPCL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY",
    "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE",
    "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK",
    "INFY", "ITC", "JSWSTEEL", "KOTAKBANK", "LT",
    "LTIMINDTECH", "M&M", "MARUTI", "NESTLEIND", "NTPC",
    "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SBIN",
    "SHRIRAMFIN", "SUNPHARMA", "TATACONSUM", "TATAMOTORS", "TATASTEEL",
    "TCS", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO"
]

# Nifty Next 50 symbols (to build Nifty 100)
NIFTY_NEXT50_SYMBOLS = [
    "ABB", "AMBUJACEM", "AUROPHARMA", "BANDHANBNK", "BANKBARODA",
    "BERGEPAINT", "BOSCHLTD", "CHOLAFIN", "COLPAL", "CONCOR",
    "CUMMINSIND", "DABUR", "DELHIVERY", "DIVISLAB", "DLF",
    "GAIL", "GODREJCP", "GODREJPROP", "HAVELLS", "ICICIPRULI",
    "ICICIGI", "INDHOTEL", "IOC", "IRCTC", "JINDALSTEL",
    "JUBLFOOD", "LUPIN", "MUTHOOTFIN", "NAUKRI", "NHPC",
    "OBEROIRLTY", "OFSS", "PAGEIND", "PERSISTENT", "PIIND",
    "PIDILITIND", "PNB", "PGHH", "RECLTD", "SAIL",
    "SBICARD", "SIEMENS", "SJVN", "SRF", "TORNTPHARM",
    "TRENT", "TVSMOTOR", "UPL", "VEDL", "ZYDUSLIFE"
]

# F&O eligible stocks — most liquid, essential for intraday trading
# Source: NSE F&O segment approved list (July 2026)
FNO_ELIGIBLE_SYMBOLS = [
    "AARTIIND", "ABB", "ABBOTINDIA", "ABCAPITAL", "ABFRL", "ACC",
    "ADANIENT", "ADANIPORTS", "ALKEM", "AMBUJACEM", "APOLLOHOSP",
    "APOLLOTYRE", "ASHOKLEY", "ASIANPAINT", "ASTRAL", "AUROPHARMA",
    "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BALKRISIND",
    "BANDHANBNK", "BANKBARODA", "BATAINDIA", "BEL", "BERGEPAINT",
    "BHARTIARTL", "BHEL", "BIOCON", "BOSCHLTD", "BPCL", "BRITANNIA",
    "BSOFT", "CANBK", "CANFINHOME", "CHAMBLFERT", "CHOLAFIN",
    "CIPLA", "COALINDIA", "COFORGE", "COLPAL", "CONCOR",
    "COROMANDEL", "CUMMINSIND", "CYIENT", "DABUR", "DALBHARAT",
    "DEEPAKNTR", "DIVISLAB", "DLF", "DRREDDY", "EICHERMOT",
    "ESCORTS", "EXIDEIND", "FEDERALBNK", "GAIL", "GLENMARK",
    "GMRAIRPORT", "GNFC", "GODREJCP", "GODREJPROP", "GRANULES",
    "GRASIM", "GSPL", "GUJGASLTD", "HAL", "HAVELLS",
    "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO",
    "HINDCOPPER", "HINDPETRO", "HINDUNILVR", "ICICIGI", "ICICIBANK",
    "ICICIPRULI", "IDEA", "IDFC", "IDFCFIRSTB", "IEX",
    "IGL", "INDHOTEL", "INDIGO", "INDUSINDBK", "INDUSTOWER",
    "INFY", "INTELLECT", "IOC", "IRCTC", "IRFC",
    "ITC", "JINDALSTEL", "JKCEMENT", "JSWENERGY", "JSWSTEEL",
    "JUBLFOOD", "KALYANKJIL", "KOTAKBANK", "KPITTECH", "L&TFH",
    "LICHSGFIN", "LICI", "LT", "LTIMINDTECH", "LUPIN",
    "M&M", "M&MFIN", "MANAPPURAM", "MARICO", "MARUTI",
    "MCX", "METROPOLIS", "MFSL", "MGL", "MOTHERSON",
    "MPHASIS", "MRF", "MUTHOOTFIN", "NATIONALUM", "NAUKRI",
    "NAM-INDIA", "NAVINFLUOR", "NESTLEIND", "NHPC", "NMDC",
    "NTPC", "OBEROIRLTY", "OFSS", "ONGC", "PAGEIND",
    "PEL", "PERSISTENT", "PETRONET", "PFC", "PHOENIXLTD",
    "PIIND", "PIDILITIND", "PNB", "POLYCAB", "POWERGRID",
    "PVRINOX", "RAMCOCEM", "RECLTD", "RELIANCE", "SAIL",
    "SBICARD", "SBILIFE", "SBIN", "SHREECEM", "SHRIRAMFIN",
    "SIEMENS", "SRF", "SUNPHARMA", "SUNTV", "SUPREME",
    "TATACHEM", "TATACOMM", "TATACONSUM", "TATAMOTORS", "TATAPOWER",
    "TATASTEEL", "TCS", "TECHM", "TITAN", "TORNTPHARM",
    "TRENT", "TVSMOTOR", "UBL", "ULTRACEMCO", "UPL",
    "VEDL", "VOLTAS", "WIPRO", "YESBANK", "ZYDUSLIFE"
]

# ---------------------------------------------------------------------------
# Cache file paths
# ---------------------------------------------------------------------------
_DIR = Path(__file__).parent
NIFTY500_CSV_PATH = _DIR / "nifty500_cache.csv"
NIFTY1000_CSV_PATH = _DIR / "nifty1000_cache.csv"
ALL_NSE_CSV_PATH = _DIR / "all_nse_cache.csv"

_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    retry=retry_if_exception_type((requests.RequestException,))
)
def _download_csv(url: str) -> Optional[pd.DataFrame]:
    """Download CSV from NSE with retry logic."""
    resp = requests.get(url, headers=_NSE_HEADERS, timeout=15)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def get_nifty50_tickers() -> list[str]:
    """Returns current Nifty 50 tickers as list of 'SYMBOL.NS' strings."""
    return [f"{s}.NS" for s in NIFTY50_SYMBOLS]


def get_nifty100_tickers() -> list[str]:
    """Returns Nifty 100 = Nifty 50 + Nifty Next 50."""
    combined = list(dict.fromkeys(NIFTY50_SYMBOLS + NIFTY_NEXT50_SYMBOLS))
    return [f"{s}.NS" for s in combined]


def get_fno_tickers() -> list[str]:
    """Returns F&O eligible stocks — most liquid, recommended for intraday."""
    return [f"{s}.NS" for s in FNO_ELIGIBLE_SYMBOLS]


def get_nifty500_tickers() -> list[str]:
    """
    Returns Nifty 500 tickers. Tries local cache → NSE archives → fallback to Nifty 100.
    """
    if NIFTY500_CSV_PATH.exists():
        try:
            df = pd.read_csv(NIFTY500_CSV_PATH)
            if "Symbol" in df.columns:
                syms = df["Symbol"].dropna().astype(str).str.strip().tolist()
                if len(syms) > 100:
                    return [f"{s}.NS" for s in syms if s]
        except Exception as e:
            print(f"Error reading Nifty 500 cache: {e}")

    for url in [
        "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
        "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
    ]:
        try:
            print(f"Downloading Nifty 500 from {url} ...")
            df = _download_csv(url)
            if df is not None and "Symbol" in df.columns:
                df.to_csv(NIFTY500_CSV_PATH, index=False)
                syms = df["Symbol"].dropna().astype(str).str.strip().tolist()
                return [f"{s}.NS" for s in syms if s]
        except Exception as e:
            print(f"Failed from {url}: {e}")

    print("Falling back to Nifty 100.")
    return get_nifty100_tickers()



def get_nifty1000_tickers() -> list[str]:
    """
    Builds a Nifty 1000 list: Nifty 500 + liquid EQ stocks from EQUITY_L.csv.
    """
    if NIFTY1000_CSV_PATH.exists():
        try:
            df = pd.read_csv(NIFTY1000_CSV_PATH)
            if "Symbol" in df.columns:
                syms = df["Symbol"].dropna().astype(str).str.strip().tolist()
                if len(syms) >= 500:
                    return [f"{s}.NS" for s in syms if s]
        except Exception as e:
            print(f"Error reading Nifty 1000 cache: {e}")

    nifty500_syms = [t.replace(".NS", "") for t in get_nifty500_tickers()]
    unique_symbols = list(dict.fromkeys(nifty500_syms))

    try:
        print("Downloading EQUITY_L to build Nifty 1000...")
        df = _download_csv("https://archives.nseindia.com/content/equities/EQUITY_L.csv")
        if df is not None and 'SYMBOL' in df.columns and ' SERIES' in df.columns:
            eq_syms = (
                df[df[' SERIES'].str.strip() == 'EQ']['SYMBOL']
                .dropna().astype(str).str.strip().tolist()
            )
            for sym in eq_syms:
                if sym and sym not in unique_symbols:
                    unique_symbols.append(sym)
                if len(unique_symbols) >= 1000:
                    break
    except Exception as e:
        print(f"Error building Nifty 1000: {e}")

    pd.DataFrame({"Symbol": unique_symbols}).to_csv(NIFTY1000_CSV_PATH, index=False)
    return [f"{s}.NS" for s in unique_symbols]


def get_all_nse_tickers() -> list[str]:
    """
    Returns all listed symbols on NSE (Series EQ).
    Tries local cache -> NSE EQUITY_L.csv -> fallback to Nifty 1000.
    """
    if ALL_NSE_CSV_PATH.exists():
        try:
            df = pd.read_csv(ALL_NSE_CSV_PATH)
            if "Symbol" in df.columns:
                syms = df["Symbol"].dropna().astype(str).str.strip().tolist()
                if len(syms) >= 1000:
                    return [f"{s}.NS" for s in syms if s]
        except Exception as e:
            print(f"Error reading all NSE cache: {e}")

    unique_symbols = [t.replace(".NS", "") for t in get_nifty1000_tickers()]

    try:
        print("Downloading EQUITY_L to fetch all NSE stocks...")
        resp = requests.get(
            "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
            headers=_NSE_HEADERS, timeout=15
        )
        if resp.status_code == 200:
            df = pd.read_csv(StringIO(resp.text))
            if 'SYMBOL' in df.columns and ' SERIES' in df.columns:
                eq_syms = (
                    df[df[' SERIES'].str.strip() == 'EQ']['SYMBOL']
                    .dropna().astype(str).str.strip().tolist()
                )
                for sym in eq_syms:
                    if sym and sym not in unique_symbols:
                        unique_symbols.append(sym)
    except Exception as e:
        print(f"Error downloading all NSE symbols: {e}")

    pd.DataFrame({"Symbol": unique_symbols}).to_csv(ALL_NSE_CSV_PATH, index=False)
    return [f"{s}.NS" for s in unique_symbols]
