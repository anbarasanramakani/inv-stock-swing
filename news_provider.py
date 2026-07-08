"""
news_provider.py
Provides news-driven swing trade recommendations.

Live news: Scraped via Google News RSS + NSE corporate announcement feed.
Fallback: Curated recent catalysts when live scraping fails.

Backtest: Historical catalyst list evaluated against actual price outcomes.
"""
import pandas as pd
import numpy as np
import datetime
import time
import xml.etree.ElementTree as ET

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

# ---------------------------------------------------------------------------
# Catalyst → NSE symbol mapping (for news → ticker matching)
# ---------------------------------------------------------------------------
CATALYST_TICKER_MAP = {
    "HFCL": "HFCL.NS",
    "NBCC": "NBCC.NS",
    "TITAN": "TITAN.NS",
    "HDFC BANK": "HDFCBANK.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "TCS": "TCS.NS",
    "TATA CONSULTANCY": "TCS.NS",
    "MAZAGON": "MAZDOCK.NS",
    "MAZDOCK": "MAZDOCK.NS",
    "HAL": "HAL.NS",
    "RVNL": "RVNL.NS",
    "RAIL VIKAS": "RVNL.NS",
    "IRFC": "IRFC.NS",
    "TATA POWER": "TATAPOWER.NS",
    "TATAPOWER": "TATAPOWER.NS",
    "TRENT": "TRENT.NS",
    "ZOMATO": "ETERNAL.NS",
}

# ---------------------------------------------------------------------------
# Fallback curated news picks (refreshed periodically)
# ---------------------------------------------------------------------------
FALLBACK_NEWS_PICKS = [
    {
        "Symbol": "HFCL.NS",
        "Headline": "HFCL secures massive ₹2,666 Crore BharatNet Phase-III contract from RVNL.",
        "Catalyst": "Order Win",
        "Sentiment": "Highly Positive",
        "Date": "2026-07-07"
    },
    {
        "Symbol": "NBCC.NS",
        "Headline": "NBCC secures three government Project Management Consultancy contracts.",
        "Catalyst": "PMC Orders",
        "Sentiment": "Positive",
        "Date": "2026-07-07"
    },
    {
        "Symbol": "TITAN.NS",
        "Headline": "Titan reports strong 41% YoY revenue growth in Q1 FY27 business update.",
        "Catalyst": "Earnings Beat",
        "Sentiment": "Positive",
        "Date": "2026-07-07"
    },
    {
        "Symbol": "HDFCBANK.NS",
        "Headline": "HDFC Bank Q1 FY27 update: healthy growth in gross advances and deposits.",
        "Catalyst": "Business Update",
        "Sentiment": "Positive",
        "Date": "2026-07-04"
    },
]

# Historical catalysts for the last 10 trading days (backtesting)
HISTORICAL_NEWS_CATALYSTS = [
    {
        "Date": "2026-06-24", "Symbol": "MAZDOCK.NS",
        "Headline": "Mazagon Dock in talks for ₹43,000 Cr submarine contract with MoD.",
        "Catalyst": "Contract Deal"
    },
    {
        "Date": "2026-06-25", "Symbol": "HAL.NS",
        "Headline": "HAL receives RFP for 156 Light Combat Helicopters.",
        "Catalyst": "RFP / Order"
    },
    {
        "Date": "2026-06-26", "Symbol": "RVNL.NS",
        "Headline": "RVNL emerges L1 bidder for ₹156 Crore Central Railway project.",
        "Catalyst": "L1 Bidder"
    },
    {
        "Date": "2026-06-30", "Symbol": "TCS.NS",
        "Headline": "TCS wins multi-million pound contract extension with UK NEST.",
        "Catalyst": "Contract Extension"
    },
    {
        "Date": "2026-07-01", "Symbol": "TRENT.NS",
        "Headline": "Trent reports record business expansion with 19% sales growth.",
        "Catalyst": "Sales Growth"
    },
    {
        "Date": "2026-07-02", "Symbol": "IRFC.NS",
        "Headline": "Railway Ministry schedules capex fast-track review via IRFC.",
        "Catalyst": "Capex Boost"
    },
    {
        "Date": "2026-07-03", "Symbol": "TATAPOWER.NS",
        "Headline": "Tata Power secures LoI for ₹950 Crore Gujarat transmission project.",
        "Catalyst": "Order Win"
    },
]

# ---------------------------------------------------------------------------
# Live News Scraper — Google News RSS
# ---------------------------------------------------------------------------
_NSE_KEYWORDS = [
    "order win", "contract win", "L1 bidder", "quarterly results",
    "earnings", "revenue growth", "acquisition", "merger",
    "capex", "dividend", "block deal", "bulk deal", "JV",
    "project award", "letter of intent", "LOI", "MoU"
]


def _fetch_google_news_rss(query: str, max_results: int = 5) -> list:
    """Fetch headlines from Google News RSS for a query."""
    if not _HAS_REQUESTS:
        return []
    try:
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall('.//item')[:max_results]:
            title = item.findtext('title', '')
            link  = item.findtext('link', '')
            pub   = item.findtext('pubDate', '')
            items.append({"title": title, "link": link, "pubDate": pub})
        return items
    except Exception:
        return []


def get_live_news_picks(all_symbols: list = None) -> list:
    """
    Attempts to scrape live news catalysts for today matching any NSE stock.
    Falls back to FALLBACK_NEWS_PICKS if scraping fails or no matches found.
    """
    if all_symbols:
        try:
            picks = scrape_live_all_nse_news(all_symbols)
            if picks:
                return picks
        except Exception as e:
            print(f"Error scraping live news: {e}")
            
    # Fallback to recent fresh announcements
    try:
        cutoff = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
        fresh = [p for p in FALLBACK_NEWS_PICKS if p.get("Date", "2000-01-01") >= cutoff]
        if fresh:
            return fresh
    except Exception:
        pass

    return FALLBACK_NEWS_PICKS


import re

def extract_ticker_from_headline(headline: str, all_symbols: list) -> str | None:
    """Matches a headline string against all known NSE symbols and custom mappings."""
    if not all_symbols:
        return None
        
    # 1. Match direct uppercase tickers from the ORIGINAL headline to prevent matching lowercase words
    words = re.findall(r'\b[A-Z]{3,10}\b', headline)
    for w in words:
        symbol_ns = f"{w}.NS"
        if symbol_ns in all_symbols:
            return symbol_ns

    headline_upper = headline.upper()

    # 2. Match common manual mappings (full company names)
    custom_mappings = {
        "RELIANCE": "RELIANCE.NS",
        "TATA CONSULTANCY": "TCS.NS",
        "INFOSYS": "INFY.NS",
        "HDFC BANK": "HDFCBANK.NS",
        "HDFCBANK": "HDFCBANK.NS",
        "ICICI BANK": "ICICIBANK.NS",
        "STATE BANK": "SBIN.NS",
        "SBI ": "SBIN.NS",
        "AXIS BANK": "AXISBANK.NS",
        "KOTAK": "KOTAKBANK.NS",
        "LARSEN & TOUBRO": "LT.NS",
        "L&T": "LT.NS",
        "MAZAGON DOCK": "MAZDOCK.NS",
        "MAZDOCK": "MAZDOCK.NS",
        "RAIL VIKAS": "RVNL.NS",
        "RVNL": "RVNL.NS",
        "BHARTI AIRTEL": "BHARTIARTL.NS",
        "AIRTEL": "BHARTIARTL.NS",
        "ADANI ENTERPRISES": "ADANIENT.NS",
        "ADANI PORTS": "ADANIPORTS.NS",
        "TITAN": "TITAN.NS",
        "MARUTI": "MARUTI.NS",
        "M&M": "M&M.NS",
        "BAJAJ AUTO": "BAJAJ-AUTO.NS",
        "BAJAJ FINANCE": "BAJFINANCE.NS",
        "HERO MOTOCORP": "HEROMOTOCO.NS",
        "ULTRATECH": "ULTRACEMCO.NS",
        "JSW STEEL": "JSWSTEEL.NS",
        "POWER GRID": "POWERGRID.NS",
        "COAL INDIA": "COALINDIA.NS",
        "APOLLO HOSPITALS": "APOLLOHOSP.NS",
        "SUN PHARMA": "SUNPHARMA.NS",
        "HINDUSTAN UNILEVER": "HINDUNILVR.NS",
        "BRITANNIA": "BRITANNIA.NS",
        "NESTLE": "NESTLEIND.NS",
        "EICHER": "EICHERMOT.NS",
        "CIPLA": "CIPLA.NS",
        "DR REDDY": "DRREDDY.NS",
        "GRASIM": "GRASIM.NS",
        "HCL TECH": "HCLTECH.NS",
        "WIPRO": "WIPRO.NS",
        "TECH MAHINDRA": "TECHM.NS",
        "BEL ": "BEL.NS",
        "BHARAT ELECTRONICS": "BEL.NS",
        "HAL ": "HAL.NS",
        "HINDUSTAN AERONAUTICS": "HAL.NS",
        "IRFC": "IRFC.NS",
        "TRENT": "TRENT.NS",
        "NBCC": "NBCC.NS",
        "HFCL": "HFCL.NS",
        "ZOMATO": "ETERNAL.NS",
    }
    
    for key, sym in custom_mappings.items():
        if key in headline_upper:
            return sym
            
    # 3. Check for stripped name matches (e.g. "TATA POWER" -> "TATAPOWER")
    headline_stripped = re.sub(r'[^A-Z0-9]', '', headline_upper)
    for sym in all_symbols:
        clean_sym = sym.replace(".NS", "")
        clean_stripped = re.sub(r'[^A-Z0-9]', '', clean_sym)
        if len(clean_stripped) >= 4 and clean_stripped in headline_stripped:
            return sym
            
    return None


def scrape_live_all_nse_news(all_symbols: list) -> list:
    """
    Queries Google News RSS, identifies NSE stock symbols from headlines,
    and returns deduplicated positive corporate catalysts.
    """
    if not _HAS_REQUESTS:
        return FALLBACK_NEWS_PICKS
        
    queries = [
        '(site:moneycontrol.com OR site:economictimes.indiatimes.com OR site:livemint.com OR site:financialexpress.com OR site:business-standard.com) ("order win" OR "contract win" OR "earnings" OR "merger" OR "dividend")',
        '(site:reddit.com/r/IndianStreetBets OR site:x.com) ("breakout" OR "multibagger" OR "bullish" OR "shares jump" OR "order win" OR "dividend")',
        '(site:moneycontrol.com OR site:economictimes.indiatimes.com OR site:livemint.com OR site:financialexpress.com OR site:business-standard.com) ("crash" OR "plunge" OR "slump" OR "tumble" OR "shares fall" OR "drop" OR "correction")'
    ]
    
    scraped_items = []
    for q in queries:
        scraped_items.extend(_fetch_google_news_rss(q, max_results=8))
        time.sleep(0.1)
        
    seen_symbols = set()
    matched_news_picks = []
    
    for item in scraped_items:
        title = item["title"]
        if " - " in title:
            title_clean = title.rsplit(" - ", 1)[0]
        else:
            title_clean = title
            
        ticker = extract_ticker_from_headline(title_clean, all_symbols)
        if ticker and ticker not in seen_symbols:
            title_lower = title_clean.lower()
            catalyst = "Corporate Catalyst"
            sentiment = "Positive"
            
            neg_keywords = ["crash", "plunge", "slump", "tumble", "fall", "drop", "down", "correction"]
            is_negative = any(kw in title_lower for kw in neg_keywords)
            
            if is_negative:
                catalyst = "Market Crash / Drop"
                sentiment = "Negative"
            elif "order" in title_lower or "contract" in title_lower or "l1" in title_lower:
                catalyst = "Order Win / Contract"
            elif "earning" in title_lower or "result" in title_lower or "revenue" in title_lower:
                catalyst = "Earnings / Results"
            elif "dividend" in title_lower:
                catalyst = "Dividend Announcement"
            elif "acquir" in title_lower or "merger" in title_lower:
                catalyst = "M&A / Deal"
            elif "capex" in title_lower:
                catalyst = "Capex Expansion"
                
            seen_symbols.add(ticker)
            matched_news_picks.append({
                "Symbol": ticker,
                "Headline": title_clean,
                "Catalyst": catalyst,
                "Sentiment": sentiment,
                "Date": datetime.date.today().isoformat(),
                "DateTime": item.get("pubDate", datetime.date.today().isoformat())
            })
            
    return matched_news_picks


# ---------------------------------------------------------------------------
# ATR helper
# ---------------------------------------------------------------------------
def _calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl  = df['High'] - df['Low']
    hc  = (df['High'] - df['Close'].shift()).abs()
    lc  = (df['Low']  - df['Close'].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# ---------------------------------------------------------------------------
# Recommendation builder
# ---------------------------------------------------------------------------
def get_today_news_recommendations(stock_data: dict, all_symbols: list = None, existing_picks: list = None) -> list:
    """
    Screens today's news picks using stock data.
    If a matched news symbol is not in stock_data, it dynamically downloads
    its historical EOD data on-the-fly, supporting news-based trades across all NSE stocks.
    Uses delta loading: preserves already computed recommendations from existing_picks cache.
    """
    import data_provider as dp
    
    picks = []
    live_picks = get_live_news_picks(all_symbols)

    # Index existing picks by headline for fast lookup
    cached_map = {}
    if existing_picks:
        for p in existing_picks:
            if "Headline" in p:
                cached_map[p["Headline"]] = p

    for news in live_picks:
        headline = news["Headline"]
        if headline in cached_map:
            # Re-use already processed recommendation (delta check)
            picks.append(cached_map[headline])
            continue
            
        symbol = news["Symbol"]
        df = None
        
        # Check cache
        if symbol in stock_data:
            df = stock_data[symbol]
        else:
            # Download on-the-fly for any NSE stock catalyst
            try:
                df = dp.get_single_stock_data(symbol, period="1y")
            except Exception as e:
                print(f"Error fetching on-the-fly EOD for {symbol}: {e}")
                
        if df is None or len(df) < 20:
            continue

        r   = df.iloc[-1]
        cmp = float(r['Close'])
        atr = _calc_atr(df).iloc[-1]
        if pd.isna(atr) or atr <= 0:
            atr = cmp * 0.02

        sentiment = news.get("Sentiment", "Positive")
        if sentiment == "Negative":
            sl     = round(cmp + 1.2 * atr, 2)
            target = round(cmp - 1.5 * atr, 2)
            rr = "1:1.25 (Short)"
        else:
            sl     = round(cmp - 1.2 * atr, 2)
            target = round(cmp + 1.5 * atr, 2)
            rr = "1:1.25 (Long)"

        picks.append({
            "Ticker":      symbol,
            "Headline":    headline,
            "Catalyst":    news["Catalyst"],
            "Price":       round(cmp, 2),
            "Entry Range": f"{round(cmp * 0.995, 2)} - {round(cmp * 1.005, 2)}",
            "Stop Loss":   sl,
            "Target":      target,
            "Risk_Reward": rr,
            "Sentiment":   sentiment,
            "DateTime":    news.get("DateTime", news.get("Date", ""))
        })

    return picks


# ---------------------------------------------------------------------------
# 10-Day News Backtest
# ---------------------------------------------------------------------------
def run_news_backtest(stock_data_dict: dict) -> list:
    """
    Evaluates historical news catalyst trades over a max 5-day holding window.
    """
    results = []

    for item in HISTORICAL_NEWS_CATALYSTS:
        symbol   = item["Symbol"]
        date_str = item["Date"]

        if symbol not in stock_data_dict:
            continue

        df = stock_data_dict[symbol]

        try:
            trigger_idx = df.index.get_indexer([pd.to_datetime(date_str)], method='nearest')[0]
        except Exception:
            continue

        if trigger_idx < 15 or trigger_idx >= len(df) - 1:
            continue

        slice_df = df.iloc[:trigger_idx + 1]
        cmp      = float(slice_df['Close'].iloc[-1])
        atr      = _calc_atr(slice_df).iloc[-1]
        if pd.isna(atr) or atr <= 0:
            atr = cmp * 0.02

        sl     = round(cmp - 1.2 * atr, 2)
        target = round(cmp + 1.5 * atr, 2)

        status      = "Active"
        days_held   = 0
        pnl_pct     = 0.0
        exit_price  = cmp
        N           = len(df)

        for check_idx in range(trigger_idx + 1, min(trigger_idx + 6, N)):
            days_held += 1
            day_high   = float(df['High'].iloc[check_idx])
            day_low    = float(df['Low'].iloc[check_idx])

            if day_low <= sl:
                status      = "Stop Loss Hit"
                exit_price  = sl
                pnl_pct     = ((sl - cmp) / cmp) * 100
                break
            elif day_high >= target:
                status      = "Target Hit"
                exit_price  = target
                pnl_pct     = ((target - cmp) / cmp) * 100
                break

        if status == "Active":
            exit_price = float(df['Close'].iloc[min(trigger_idx + 5, N - 1)])
            pnl_pct    = ((exit_price - cmp) / cmp) * 100

        results.append({
            "Trigger Date": date_str,
            "Ticker":       symbol.replace(".NS", ""),
            "Catalyst":     item["Catalyst"],
            "Headline":     item["Headline"],
            "Entry Price":  round(cmp, 2),
            "Target":       target,
            "Stop Loss":    sl,
            "Current/Exit": round(exit_price, 2),
            "P&L (%)":      round(pnl_pct, 2),
            "Status":       status,
            "Days Held":    days_held,
        })

    return results
