"""
institutional.py
Fetches FII/FPI macro sentiment and cross-references bulk deals against known
institutional buyers (Mutual Funds, LIC, FIIs) and superstar retail investors.

HFT prop-desk and arbitrage firms are excluded from Tier-1 conviction matching
using exact-match firm names (no fuzzy partial strings) + minimum qty filter.
"""
import pandas as pd
import streamlit as st
from nselib.nsdl_fpi import fetch_nsdl_fpi_latest_investment_activity
from nselib.capital_market import bulk_deal_data

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
def get_latest_fii_sentiment():
    """
    Returns (net_flow_crores: float, report_date: str) or (None, None).
    First tries real-time daily FII/DII provisional data from nsepython.
    Falls back to NSDL historical FPI data on failure.
    """
    # 1. Try real-time daily provisional FII/FPI activity from NSE
    try:
        from nsepython import nse_fiidii
        df = nse_fiidii(mode="pandas")
        if df is not None and not df.empty and 'category' in df.columns:
            # Look for FII/FPI category
            fii_row = df[df['category'].str.upper().str.contains('FII|FPI', na=False)]
            if not fii_row.empty:
                net_val = fii_row['netValue'].iloc[0]
                net_flow = float(str(net_val).replace(',', '').strip())
                report_date = fii_row['date'].iloc[0]
                return round(net_flow, 2), str(report_date)
    except Exception as e:
        print(f"[FII Info] Realtime NSE FII fetch failed: {e}. Trying NSDL fallback...")

    # 2. Fallback to NSDL FPI investment activity
    try:
        df = fetch_nsdl_fpi_latest_investment_activity()
        if df is not None and not df.empty and 'ASSET_CLASS' in df.columns:
            equity = df[df['ASSET_CLASS'].str.upper() == 'EQUITY']
            if not equity.empty:
                net_flow = equity['NET_INVESTMENT_RS_CR'].sum()
                report_date = equity['REPORT_DATE'].iloc[0]
                return round(net_flow, 2), str(report_date)
    except Exception as fallback_err:
        print(f"[FII Fallback] NSDL FPI fallback failed: {fallback_err}")
        
    return None, None


def get_recent_bulk_deals() -> pd.DataFrame | None:
    """
    Fetches bulk deals for the last 7 days.
    Returns cleaned DataFrame or None.
    """
    try:
        df = bulk_deal_data(period='1W')
        if df is not None and not df.empty:
            df = df.copy()
            df['Symbol']   = df['Symbol'].str.strip().str.upper()
            df['Buy/Sell']  = df['Buy/Sell'].str.strip().str.upper()
            df['ClientName'] = df['ClientName'].str.strip().str.upper()
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
