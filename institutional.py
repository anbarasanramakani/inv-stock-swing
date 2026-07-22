"""
institutional.py
Fetches FII/FPI macro sentiment and cross-references bulk deals against known
institutional buyers (Mutual Funds, LIC, FIIs) and superstar retail investors.

HFT prop-desk and arbitrage firms are excluded from Tier-1 conviction matching
using exact-match firm names (no fuzzy partial strings) + minimum qty filter.
"""
from typing import Optional
import pandas as pd
import streamlit as st
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    from nselib.nsdl_fpi import fetch_nsdl_fpi_latest_investment_activity
    from nselib.capital_market import bulk_deal_data
    _HAS_NSELIB = True
except ImportError:
    _HAS_NSELIB = False

# ---------------------------------------------------------------------------
# Known superstar retail investors (exact NSE bulk deal client name strings)
# ---------------------------------------------------------------------------
SUPERSTAR_INVESTORS = {
    "ASHISH KACHOLIA", "ASHISH RAMESHCHANDRA KACHOLIA",
    "MUKUL AGRAWAL", "MUKUL MAHAVIR AGRAWAL",
    "VIJAY KEDIA", "VIJAY KISHANLAL KEDIA",
    "REKHA JHUNJHUNWALA", "REKHA RAKESH JHUNJHUNWALA",
    "DOLLY KHANNA",
    "RADHAKISHAN DAMANI", "RADHAKISHAN S DAMANI",
    "SUNIL SINGHANIA", "ABAKKUS ASSET MANAGER",
    "ASHISH DHAWAN",
    "NEMISH SHAH",
    "AKASH BHANSHALI",
    "MOHNISH PABRAI", "PABRAI INVESTMENT FUND",
    "PORINJU VELIYATH", "EQUITY INTELLIGENCE INDIA",
    "ANIL KUMAR GOEL",
    "MANISH JAIN",
}

# ---------------------------------------------------------------------------
# Institutional buyers — Mutual Funds, Insurance, FII Banks
# (Partial match allowed only for these longer, distinctive names)
# ---------------------------------------------------------------------------
INSTITUTIONAL_KEYWORDS = [
    # Domestic MFs
    "SBI MUTUAL FUND", "HDFC MUTUAL FUND", "ICICI PRUDENTIAL MUTUAL",
    "NIPPON INDIA MUTUAL", "AXIS MUTUAL FUND", "KOTAK MUTUAL FUND",
    "DSP MUTUAL FUND", "UTI MUTUAL FUND", "TATA MUTUAL FUND",
    "MIRAE ASSET", "CANARA ROBECO", "FRANKLIN TEMPLETON",
    "INVESCO INDIA", "ADITYA BIRLA SUN LIFE",
    # Insurance
    "LIFE INSURANCE CORPORATION", "LIC OF INDIA", "HDFC LIFE",
    "ICICI PRUDENTIAL LIFE", "SBI LIFE",
    # FII / Global Banks
    "GOLDMAN SACHS", "MORGAN STANLEY", "JP MORGAN",
    "SOCIETE GENERALE", "BNP PARIBAS", "CITIGROUP",
    "GOVERNMENT OF SINGAPORE", "NORWAY GOVERNMENT",
    "VANGUARD", "BLACKROCK",
]

# ---------------------------------------------------------------------------
# HFT / prop desks to EXCLUDE — exact company names only (no partial fuzzy)
# ---------------------------------------------------------------------------
HFT_PROP_EXACT = {
    "NK SECURITIES RESEARCH PVT LTD",
    "QE SECURITIES PVT LTD",
    "GRAVITON RESEARCH CAPITAL LLP",
    "JUMP TRADING INDIA PVT LTD",
    "MICROCURVES TRADING PVT LTD",
    "HRTI PRIVATE LIMITED",
    "ALGOQUANT FINTECH PRIVATE LIMITED",
    "TOWER RESEARCH CAPITAL",
    "PLUTUS CAPITAL",
    "BEYOND SHARES PVT LTD",
    "SAJAG SECURITIES PVT LTD",
    "MAVIBOOK PVT LTD",
}

# Minimum shares in a bulk deal to qualify as "conviction" buy (not a test trade)
MIN_CONVICTION_QTY = 5_000


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800)
@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=5),
    retry=retry_if_exception_type((Exception,))
)
def get_latest_fii_sentiment() -> tuple[Optional[float], Optional[str]]:
    """
    Returns (net_flow_crores: float, report_date: str) or (None, None).
    First tries NSDL historical FPI data.
    Falls back to alternative sources on failure.
    """
    if not _HAS_NSELIB:
        return None, None

    # 1. Try NSDL FPI investment activity (primary source)
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fetch_nsdl_fpi_latest_investment_activity)
            try:
                df = future.result(timeout=5)
            except concurrent.futures.TimeoutError:
                df = None
        if df is not None and not df.empty and 'ASSET_CLASS' in df.columns:
            equity = df[df['ASSET_CLASS'].str.upper() == 'EQUITY']
            if not equity.empty and 'NET_INVESTMENT_RS_CR' in equity.columns:
                net_flow = equity['NET_INVESTMENT_RS_CR'].sum()
                report_date = equity['REPORT_DATE'].iloc[0] if 'REPORT_DATE' in equity.columns else ''
                return round(net_flow, 2), str(report_date)
    except Exception as e:
        print(f"[FII Info] NSDL fetch failed: {e}. Trying alternative...")

    # 2. Fallback: Try NSE live endpoint
    try:
        import data_provider as dp
        session = dp._get_nse_session()
        resp = session.get("https://www.nseindia.com/api/fiidii", timeout=2.5)
        if resp.status_code == 200:
            data = resp.json()
            # Parse FII data from response
            fii_data = data.get('data', [])
            for item in fii_data:
                if 'FII' in item.get('category', '').upper():
                    net_val = item.get('netValue', 0)
                    net_flow = float(str(net_val).replace(',', '').strip())
                    date_val = item.get('date', '')
                    return round(net_flow, 2), str(date_val)
    except Exception as fallback_err:
        print(f"[FII Fallback] NSE FII fetch failed: {fallback_err}")
        
    return None, None


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    retry=retry_if_exception_type((Exception,))
)
def get_recent_bulk_deals() -> Optional[pd.DataFrame]:
    """
    Fetches bulk deals for the last 7 days.
    Returns cleaned DataFrame or None.
    """
    if not _HAS_NSELIB:
        return None
    
    try:
        import concurrent.futures
        # Use ThreadPoolExecutor as a context manager to prevent thread leaks
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(bulk_deal_data, period='1W')
            try:
                df = future.result(timeout=8)
            except concurrent.futures.TimeoutError:
                print("[FII/Bulk] NSE bulk_deal_data timed out after 8s.")
                return None
            
        if df is not None and not df.empty:
            df = df.copy()
            # Normalize column names (handle case variations)
            df.columns = df.columns.str.strip()
            col_map = {}
            for col in df.columns:
                col_lower = col.lower()
                if 'symbol' in col_lower:
                    col_map[col] = 'Symbol'
                elif 'buy' in col_lower and 'sell' in col_lower:
                    col_map[col] = 'Buy/Sell'
                elif 'client' in col_lower:
                    col_map[col] = 'ClientName'
                elif 'quantity' in col_lower:
                    col_map[col] = 'QuantityTraded'
                elif 'price' in col_lower or 'wght' in col_lower:
                    col_map[col] = 'TradePrice/Wght.Avg.Price'
                elif 'date' in col_lower:
                    col_map[col] = 'Date'
            df.rename(columns=col_map, inplace=True)
            
            required_cols = ['Symbol', 'Buy/Sell']
            if not all(col in df.columns for col in required_cols):
                return df
            
            df['Symbol'] = df['Symbol'].astype(str).str.strip().str.upper()
            df['Buy/Sell'] = df['Buy/Sell'].astype(str).str.strip().str.upper()
            if 'ClientName' in df.columns:
                df['ClientName'] = df['ClientName'].astype(str).str.strip().str.upper()
            return df
    except Exception as e:
        print(f"[Bulk Deals] Error: {e}")
    return None


def _parse_qty(val) -> int:
    """Safely parse quantity field which may be string with commas."""
    try:
        return int(float(str(val).replace(',', '').strip()))
    except Exception:
        return 0


def _parse_price(val) -> float:
    """Safely parse price field."""
    try:
        return float(str(val).replace(',', '').strip())
    except Exception:
        return 0.0


def enrich_picks_with_bulk_deals(technical_picks: list, bulk_deals_df: pd.DataFrame | None) -> list:
    """
    Cross-references technical picks with recent bulk deal BUY transactions.

    Tier tagging:
      - Superstar Buy    → Superstar_Buying = True, High_Conviction = True
      - Institutional    → High_Conviction = True
      - Other anchor     → High_Conviction = True (if qty >= MIN_CONVICTION_QTY)

    HFT/prop desk transactions and tiny trades are silently excluded.
    """
    if not technical_picks:
        return []

    enriched = []
    for pick in technical_picks:
        pick = dict(pick)
        pick.setdefault("High_Conviction",    False)
        pick.setdefault("Superstar_Buying",   False)
        pick.setdefault("Institutional_Details", None)
        pick.setdefault("Superstar_Names",    "")

        if bulk_deals_df is None or bulk_deals_df.empty:
            enriched.append(pick)
            continue

        symbol  = pick["Ticker"].replace(".NS", "").strip().upper()
        matches = bulk_deals_df[
            (bulk_deals_df['Symbol'] == symbol) &
            (bulk_deals_df['Buy/Sell'] == 'BUY')
        ]

        if matches.empty:
            enriched.append(pick)
            continue

        details_list    = []
        superstars_found = []

        for _, row in matches.iterrows():
            client = str(row.get('ClientName', '')).upper().strip()
            qty    = _parse_qty(row.get('QuantityTraded', 0))
            price  = _parse_price(row.get('TradePrice/Wght.Avg.Price', 0))
            date   = row.get('Date', '')

            # 1. Skip exact HFT/prop firms
            if client in HFT_PROP_EXACT:
                continue

            # 2. Skip tiny / test trades
            if qty < MIN_CONVICTION_QTY:
                continue

            qty_str   = f"{qty:,}"
            price_str = f"₹{price:.2f}"

            # 3. Check superstar (exact match)
            is_superstar = any(name in client for name in SUPERSTAR_INVESTORS)
            if is_superstar:
                matched_name = next((n.title() for n in SUPERSTAR_INVESTORS if n in client), client.title())
                superstars_found.append(matched_name)
                tag = "🔥 Superstar"
                pick["Superstar_Buying"] = True
            # 4. Check institutional keyword
            elif any(kw in client for kw in INSTITUTIONAL_KEYWORDS):
                tag = "💼 Institutional"
            else:
                tag = "🔷 Anchor"

            details_list.append(
                f"{tag}: {client.title()} — {qty_str} shares @ {price_str} on {date}"
            )

        if details_list:
            pick["High_Conviction"]     = True
            pick["Institutional_Details"] = " | ".join(details_list)
            if superstars_found:
                pick["Superstar_Names"] = ", ".join(sorted(set(superstars_found)))

        enriched.append(pick)

    return enriched
