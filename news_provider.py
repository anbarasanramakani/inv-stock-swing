"""
news_provider.py
Provides news-driven swing trade recommendations.

Live news: Scraped via Google News RSS + NSE corporate announcement feed.
Fallback: Curated recent catalysts when live scraping fails.

Backtest: Historical catalyst list evaluated against actual price outcomes.
"""
from typing import List, Dict
import pandas as pd
import datetime
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor

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
    "ICICI BANK": "ICICIBANK.NS",
    "SBI": "SBIN.NS",
    "STATE BANK": "SBIN.NS",
    "SOUTH INDIAN BANK": "SOUTHBANK.NS",
    "SOUTHBANK": "SOUTHBANK.NS",
    "INDUSIND BANK": "INDUSINDBANK.NS",
    "AXIS BANK": "AXISBANK.NS",
    "KOTAK BANK": "KOTAKBANK.NS",
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
def _get_fallback_news_picks() -> List[Dict]:
    """Returns dynamic fallback news picks with today's date."""
    today = datetime.date.today().isoformat()
    return [
        {
            "Symbol": "SOUTHBANK.NS",
            "Headline": "South Indian Bank under pressure as deposit growth and credit quality concerns weigh on sentiment.",
            "Catalyst": "Banking Stress / Credit Quality",
            "Sentiment": "Negative",
            "Date": today,
            "DateTime": today
        },
        {
            "Symbol": "HFCL.NS",
            "Headline": "HFCL secures massive ₹2,666 Crore BharatNet Phase-III contract from RVNL.",
            "Catalyst": "Order Win",
            "Sentiment": "Highly Positive",
            "Date": today,
            "DateTime": today
        },
        {
            "Symbol": "NBCC.NS",
            "Headline": "NBCC secures three government Project Management Consultancy contracts.",
            "Catalyst": "PMC Orders",
            "Sentiment": "Positive",
            "Date": today,
            "DateTime": today
        },
        {
            "Symbol": "TITAN.NS",
            "Headline": "Titan reports strong 41% YoY revenue growth in Q1 FY27 business update.",
            "Catalyst": "Earnings Beat",
            "Sentiment": "Positive",
            "Date": today,
            "DateTime": today
        },
        {
            "Symbol": "HDFCBANK.NS",
            "Headline": "HDFC Bank Q1 FY27 update: healthy growth in gross advances and deposits.",
            "Catalyst": "Business Update",
            "Sentiment": "Positive",
            "Date": today,
            "DateTime": today
        },
    ]

FALLBACK_NEWS_PICKS = _get_fallback_news_picks()

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
# Broker picks extraction
# ---------------------------------------------------------------------------
BROKER_KEYWORDS = [
    "Motilal Oswal", "Kotak Securities", "Kotak", "ICICI Direct", "ICICI Securities", "ICICI",
    "Morgan Stanley", "Jefferies", "Goldman Sachs", "Goldman", "CLSA", "Credit Suisse",
    "Nomura", "Axis Capital", "Axis Securities", "Axis", "Edelweiss", "HSBC", "UBS",
    "Macquarie", "JM Financial", "HDFC Securities", "HDFC", "Nuvama", "Elara Capital",
    "Elara", "IDBI Capital", "SBI Securities", "Angel One", "Sharekhan", "Geojit",
    "BOB Capital", "Centrum", "Prabhudas Lilladher", "Anand Rathi", "SMC Global",
    "IndusInd", "BNP Paribas", "Deutsche Bank", "Citigroup", "JPMorgan", "Emkay",
    "Incred", "Systematix", "Monarch Networth", "Antique", "Choice Broking"
]


def _parse_broker_from_title(title: str) -> str:
    """Try to guess the broker name from a headline using known broker keywords."""
    t = title or ""
    for b in BROKER_KEYWORDS:
        if re.search(r'\b' + re.escape(b) + r'\b', t, re.IGNORECASE):
            return b
    # Pattern match: E.g., 'XYZ Securities', 'ABC Broking', 'DEF Capital'
    m = re.search(r"\b([A-Z][a-zA-Z0-9]+\s+(?:Securities|Capital|Broking|Brokerage|Financial|Wealth|Equities|Direct))\b", t)
    if m:
        return m.group(1)
    return "Institutional Brokerage"


def _extract_target_price(title: str):
    """Extract a numeric target price from headline if present."""
    m = re.search(r"(?:target(?: price)?|tp)[:\s]*₹?\s*([0-9,]+(?:\.[0-9]+)?)", title, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(',', ''))
        except Exception:
            return None
    # Common pattern: 'raises target to 500' or 'cuts target to 250' or 'target Rs 1200'
    m2 = re.search(r"(?:to|rs\.?|inr)\s+₹?\s*([0-9,]+(?:\.[0-9]+)?)", title, re.IGNORECASE)
    if m2:
        try:
            val = float(m2.group(1).replace(',', ''))
            if val > 10:  # avoid matching small numbers like dates
                return val
        except Exception:
            return None
    return None


def fetch_broker_calls(all_symbols: list = None, max_items: int = 40) -> list:
    """Fetch broker upgrade/downgrade/target calls from Google News RSS and return structured picks."""
    if not _HAS_REQUESTS:
        return []

    queries = [
        '("buy call" OR "buy target" OR "target price" OR "initiates coverage" OR "raises target" OR "brokerage recommendation") (stock OR shares OR nse OR bse)',
        '("recommends buy" OR "cuts target" OR "target Rs" OR "target INR" OR "broker call") (stock OR shares)'
    ]

    items = []
    try:
        for q in queries:
            items.extend(_fetch_google_news_rss(q, max_results=max_items))
    except Exception:
        pass

    results = []
    seen = set()
    for it in items:
        title = it.get('title', '')
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)

        broker = _parse_broker_from_title(title)
        ticker = extract_ticker_from_headline(title, all_symbols or [])
        target = _extract_target_price(title)
        
        # Determine recommendation action
        t_lower = title.lower()
        if any(w in t_lower for w in ['buy', 'upgrade', 'raises', 'bullish', 'outperform']):
            action = 'BUY / UPGRADE'
        elif any(w in t_lower for w in ['sell', 'downgrade', 'cuts', 'bearish', 'underperform']):
            action = 'SELL / DOWNGRADE'
        elif 'target' in t_lower:
            action = 'TARGET REVISION'
        else:
            action = 'COVERAGE'

        pub = it.get('pubDate') or it.get('pub_date') or it.get('published_at') or ''
        dt = pub
        try:
            parsed = _parse_news_datetime(pub)
            dt = parsed.isoformat()
            date_only = parsed.date().isoformat()
        except Exception:
            date_only = (pub or '')[:10]

        results.append({
            'Ticker': ticker or 'GENERAL',
            'Headline': title,
            'Broker': broker,
            'Action': action,
            'Target': target if target else 'N/A',
            'Link': it.get('link', ''),
            'DateTime': dt,
            'Date': date_only,
            'Source': it.get('source', 'Google News')
        })

    return sort_news_items(results)


def prune_cache_by_days(entries: list, days: int = 30, date_key: str = 'Date') -> list:
    """Keep only entries with date_key within the last `days` days. If parsing fails, keep the entry.
    Returns pruned list.
    """
    if not entries:
        return []
    out = []
    try:
        cutoff = datetime.date.today() - datetime.timedelta(days=days)
        for e in entries:
            d = e.get(date_key) or e.get('DateTime') or ''
            try:
                parsed = _parse_news_datetime(d)
                if parsed.date() >= cutoff:
                    out.append(e)
            except Exception:
                # if can't parse, keep the entry to avoid accidental loss
                out.append(e)
    except Exception:
        return entries
    return out

# ---------------------------------------------------------------------------
# Live News Scraper — Google News RSS
# ---------------------------------------------------------------------------
_NSE_KEYWORDS = [
    "order win", "contract win", "L1 bidder", "quarterly results",
    "earnings", "revenue growth", "acquisition", "merger",
    "capex", "dividend", "block deal", "bulk deal", "JV",
    "project award", "letter of intent", "LOI", "MoU",
    "RBI", "loan growth", "deposit growth", "asset quality",
    "guidance", "buyback", "fundraise", "approval", "policy",
    "tariff", "trade deal", "production", "capacity expansion",
    "FII", "outflow", "inflation", "rate cut"
]


def _fetch_google_news_rss(query: str, max_results: int = 5) -> list:
    """Fetch headlines from Google News RSS for a query."""
    if not _HAS_REQUESTS:
        return []
    try:
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, timeout=8, headers=headers)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall('.//item')[:max_results]:
            title = item.findtext('title', '')
            link  = item.findtext('link', '')
            pub   = item.findtext('pubDate', '')
            items.append({"title": title, "link": link, "pubDate": pub, "source": "Google News"})
        return items
    except Exception:
        return []


def _fetch_economic_times_rss(max_results: int = 10) -> list:
    """Fetch top stories from Economic Times RSS."""
    if not _HAS_REQUESTS:
        return []
    try:
        url = "https://economictimes.indiatimes.com/markets/rssfeed/21705445.cms"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, timeout=8, headers=headers)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall('.//item')[:max_results]:
            title = item.findtext('title', '')
            link  = item.findtext('link', '')
            pub   = item.findtext('pubDate', '')
            items.append({"title": title, "link": link, "pubDate": pub, "source": "Economic Times"})
        return items
    except Exception:
        return []


def _fetch_moneycontrol_rss(max_results: int = 10) -> list:
    """Fetch top stories from Moneycontrol RSS."""
    if not _HAS_REQUESTS:
        return []
    try:
        url = "https://www.moneycontrol.com/rss/marketnews.xml"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, timeout=8, headers=headers)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall('.//item')[:max_results]:
            title = item.findtext('title', '')
            link  = item.findtext('link', '')
            pub   = item.findtext('pubDate', '')
            items.append({"title": title, "link": link, "pubDate": pub, "source": "Moneycontrol"})
        return items
    except Exception:
        return []


def _fetch_livemint_rss(max_results: int = 10) -> list:
    """Fetch top market stories from Livemint RSS."""
    if not _HAS_REQUESTS:
        return []
    try:
        url = "https://www.livemint.com/rss/market_rss.xml"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, timeout=8, headers=headers)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall('.//item')[:max_results]:
            title = item.findtext('title', '')
            link  = item.findtext('link', '')
            pub   = item.findtext('pubDate', '')
            items.append({"title": title, "link": link, "pubDate": pub, "source": "Livemint"})
        return items
    except Exception:
        return []


def _fetch_nse_announcements() -> list:
    """Fetch latest corporate announcements from NSE India."""
    if not _HAS_REQUESTS:
        return []
    try:
        url = "https://www.nseindia.com/api/corporate-announcements?index=equities"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.nseindia.com/"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        items = []
        for ann in data.get('data', [])[:15]:
            headline = ann.get('subject', '')
            if headline:
                items.append({
                    "title": headline,
                    "link": f"https://www.nseindia.com{ann.get('link', '')}",
                    "pubDate": ann.get('date', ''),
                    "source": "NSE Announcements"
                })
        return items
    except Exception:
        return []


def _fetch_news_sources(query: str, max_results: int = 5) -> list:
    """Fetch from multiple news sources and return normalized items without blocking the UI."""
    items = []
    try:
        # Google News with query
        items.extend(_fetch_google_news_rss(query, max_results=max_results))
    except Exception:
        pass
    
    return items


def fetch_news_from_all_sources(all_symbols: list = None, max_items: int = 50) -> list:
    """
    Fetch news from multiple sources concurrently.
    Returns deduplicated and sorted news items.
    """
    if not _HAS_REQUESTS:
        return FALLBACK_NEWS_PICKS
    
    scraped_items = []
    
    # Fetch from multiple sources concurrently
    try:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(_fetch_economic_times_rss, 10): "Economic Times",
                executor.submit(_fetch_moneycontrol_rss, 10): "Moneycontrol",
                executor.submit(_fetch_livemint_rss, 10): "Livemint",
                executor.submit(_fetch_nse_announcements): "NSE",
            }
            
            timeout = 15  # Total timeout for all requests
            start_time = time.time()
            
            for future in futures:
                try:
                    remaining_time = max(1, timeout - (time.time() - start_time))
                    items = future.result(timeout=remaining_time)
                    scraped_items.extend(items)
                except Exception:
                    continue
    except Exception as e:
        print(f"Error fetching from multiple sources: {e}")
    
    # Also fetch Google News with market-specific queries
    market_queries = [
        'NIFTY 50 OR Sensex OR "Indian stock market"',
        'NSE OR National Stock Exchange',
        '"FII" OR "foreign investors" OR "institutional investing"',
        'earnings OR results OR quarterly results India',
        'RBI OR "monetary policy" OR "interest rate"'
    ]
    
    try:
        with ThreadPoolExecutor(max_workers=min(3, len(market_queries))) as executor:
            futures = [executor.submit(_fetch_google_news_rss, q, 8) for q in market_queries]
            for future in futures:
                try:
                    scraped_items.extend(future.result(timeout=10))
                except Exception:
                    continue
    except Exception:
        pass
    
    return scraped_items


def _parse_news_datetime(value) -> datetime.datetime:
    """Normalize different news date formats into a comparable datetime object."""
    if not value:
        return datetime.datetime.min
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return datetime.datetime.min
        try:
            return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            pass
        try:
            return datetime.datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
        try:
            return datetime.datetime.strptime(text, "%Y-%m-%d")
        except Exception:
            pass
        try:
            parsed = parsedate_to_datetime(text)
            if parsed is not None:
                return parsed.replace(tzinfo=None)
        except Exception:
            pass
    return datetime.datetime.min


def sort_news_items(items: list) -> list:
    """Return news items sorted newest-first by their DateTime or Date field."""
    return sorted(items, key=lambda item: _parse_news_datetime(item.get("DateTime") or item.get("Date")), reverse=True)


def get_news_preview(all_symbols: list = None, existing_picks: list = None) -> list:
    """Fast non-blocking preview using cached/fallback news items first."""
    if existing_picks:
        preview = []
        for item in existing_picks[:8]:
            if item.get("Headline"):
                preview.append(item)
        if preview:
            return sort_news_items(preview)

    try:
        cutoff = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
        fresh = [p for p in FALLBACK_NEWS_PICKS if p.get("Date", "2000-01-01") >= cutoff]
        if fresh:
            return sort_news_items(fresh)
    except Exception:
        pass

    return sort_news_items(FALLBACK_NEWS_PICKS[:6])


def get_live_news_picks(all_symbols: list = None) -> list:
    """
    Attempts to scrape live news catalysts for today matching any NSE stock.
    Uses multiple sources and falls back quickly to cached/fresh data.
    """
    try:
        # Fetch from all sources
        scraped_items = fetch_news_from_all_sources(all_symbols, max_items=50)
        
        if scraped_items:
            # Process and categorize the scraped items
            return scrape_live_all_nse_news_from_items(scraped_items, all_symbols)
    except Exception as e:
        print(f"Error scraping live news: {e}")

    return get_news_preview(all_symbols=all_symbols)


def scrape_live_all_nse_news_from_items(scraped_items: list, all_symbols: list) -> list:
    """
    Process raw scraped news items from multiple sources into structured news picks.
    """
    seen_keys = set()
    matched_news_picks = []
    
    for item in scraped_items:
        title = item.get("title", "")
        if " - " in title:
            title_clean = title.rsplit(" - ", 1)[0]
        else:
            title_clean = title
            
        title_lower = title_clean.lower()
        ticker = extract_ticker_from_headline(title_clean, all_symbols or [])
        key = (ticker or "MARKET", title_lower)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        catalyst = "Corporate Catalyst"
        sentiment = "Positive"
        
        neg_keywords = ["crash", "plunge", "slump", "tumble", "fall", "drop", "down", "correction", "stress", "outflow", "rbi action", "asset quality", "credit quality", "deposit growth", "banking stress"]
        pos_keywords = ["soar", "gain", "rise", "rebound", "rally", "surge", "up", "bullish", "record high", "advance", "jump", "high", "growth", "win", "award"]
        
        is_negative = any(kw in title_lower for kw in neg_keywords)
        is_positive = any(kw in title_lower for kw in pos_keywords)
        
        if is_negative:
            catalyst = "Market Crash / Outflow"
            sentiment = "Negative"
        elif is_positive:
            catalyst = "Market Rally / Positive Outlook"
            sentiment = "Positive"
            
        if "order" in title_lower or "contract" in title_lower or "l1" in title_lower or "bidder" in title_lower:
            catalyst = "Order Win / Contract"
        elif "earning" in title_lower or "result" in title_lower or "revenue" in title_lower:
            catalyst = "Earnings / Results"
        elif "dividend" in title_lower:
            catalyst = "Dividend Announcement"
        elif "acquir" in title_lower or "merger" in title_lower:
            catalyst = "M&A / Deal"
        elif "capex" in title_lower or "capacity" in title_lower:
            catalyst = "Capex Expansion"
        elif "guidance" in title_lower:
            catalyst = "Earnings / Guidance"
        elif "rbi" in title_lower or "policy" in title_lower or "rate cut" in title_lower:
            catalyst = "Policy / Macro Catalyst"
        elif "FII" in title_clean or "foreign" in title_lower:
            catalyst = "FII / Foreign Investment"

        pub_date = item.get("pubDate", datetime.date.today().isoformat())
        
        if ticker:
            matched_news_picks.append({
                "Symbol": ticker,
                "Ticker": ticker,
                "Headline": title_clean,
                "Catalyst": catalyst,
                "Sentiment": sentiment,
                "Date": pub_date,
                "DateTime": pub_date,
                "Scope": "Stock",
                "Source": item.get("source", "Unknown")
            })
        else:
            matched_news_picks.append({
                "Symbol": "",
                "Ticker": "",
                "Headline": title_clean,
                "Catalyst": catalyst if catalyst != "Corporate Catalyst" else "Market / Macro Catalyst",
                "Sentiment": sentiment,
                "Date": pub_date,
                "DateTime": pub_date,
                "Scope": "Market",
                "Source": item.get("source", "Unknown")
            })
            
    return sort_news_items(matched_news_picks)





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
        "SOUTH INDIAN BANK": "SOUTHBANK.NS",
        "SOUTHBANK": "SOUTHBANK.NS",
        "INDUSIND BANK": "INDUSINDBANK.NS",
        "KOTAK BANK": "KOTAKBANK.NS",
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
    Queries multiple Google News RSS searches, identifies NSE stock symbols from headlines,
    and returns deduplicated news catalysts for both stock-specific and market-wide events.
    """
    if not _HAS_REQUESTS:
        return FALLBACK_NEWS_PICKS

    queries = [
        '(site:moneycontrol.com OR site:economictimes.indiatimes.com OR site:livemint.com OR site:financialexpress.com OR site:business-standard.com) ("order win" OR "contract win" OR "earnings" OR "results" OR "revenue growth" OR "dividend" OR "capex" OR "merger" OR "acquisition" OR "guidance" OR "buyback" OR "loan growth" OR "deposit growth" OR "RBI" OR "FII")',
        '(site:moneycontrol.com OR site:economictimes.indiatimes.com OR site:livemint.com OR site:financialexpress.com OR site:business-standard.com) ("crash" OR "plunge" OR "slump" OR "tumble" OR "shares fall" OR "drop" OR "correction" OR "banking stress" OR "credit quality" OR "asset quality" OR "outflow" OR "rate cut" OR "policy")',
        '(site:moneycontrol.com OR site:economictimes.indiatimes.com OR site:livemint.com OR site:financialexpress.com OR site:business-standard.com) ("government order" OR "project award" OR "LoI" OR "approval" OR "MoU" OR "tariff" OR "trade deal" OR "production" OR "capacity expansion")',
        '(site:moneycontrol.com OR site:economictimes.indiatimes.com OR site:livemint.com OR site:financialexpress.com OR site:business-standard.com) ("stock market" OR "sensex" OR "nifty" OR "indian market" OR "rebound" OR "gain" OR "rise" OR "rally" OR "soar" OR "plunge" OR "crash" OR "advance")'
    ]

    scraped_items = []
    try:
        with ThreadPoolExecutor(max_workers=min(4, len(queries))) as executor:
            futures = [executor.submit(_fetch_news_sources, q, 6) for q in queries]
            for future in futures:
                scraped_items.extend(future.result(timeout=8))
    except Exception:
        for q in queries[:2]:
            scraped_items.extend(_fetch_news_sources(q, 4))

    seen_keys = set()
    matched_news_picks = []
    
    for item in scraped_items:
        title = item["title"]
        if " - " in title:
            title_clean = title.rsplit(" - ", 1)[0]
        else:
            title_clean = title
            
        title_lower = title_clean.lower()
        ticker = extract_ticker_from_headline(title_clean, all_symbols)
        key = (ticker or "MARKET", title_lower)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        catalyst = "Corporate Catalyst"
        sentiment = "Positive"
        
        neg_keywords = ["crash", "plunge", "slump", "tumble", "fall", "drop", "down", "correction", "stress", "outflow", "rbi action", "asset quality", "credit quality", "deposit growth"]
        pos_keywords = ["soar", "gain", "rise", "rebound", "rally", "surge", "up", "bullish", "record high", "advance", "jump", "high"]
        
        is_negative = any(kw in title_lower for kw in neg_keywords)
        is_positive = any(kw in title_lower for kw in pos_keywords)
        
        if is_negative:
            catalyst = "Market Crash / Outflow"
            sentiment = "Negative"
        elif is_positive:
            catalyst = "Market Rally / Positive Outlook"
            sentiment = "Positive"
            
        if "order" in title_lower or "contract" in title_lower or "l1" in title_lower:
            catalyst = "Order Win / Contract"
        elif "earning" in title_lower or "result" in title_lower or "revenue" in title_lower:
            catalyst = "Earnings / Results"
        elif "dividend" in title_lower:
            catalyst = "Dividend Announcement"
        elif "acquir" in title_lower or "merger" in title_lower:
            catalyst = "M&A / Deal"
        elif "capex" in title_lower or "capacity" in title_lower:
            catalyst = "Capex Expansion"
        elif "guidance" in title_lower:
            catalyst = "Earnings / Guidance"
        elif "rbi" in title_lower or "policy" in title_lower or "rate cut" in title_lower:
            catalyst = "Policy / Macro Catalyst"

        if ticker:
            matched_news_picks.append({
                "Symbol": ticker,
                "Ticker": ticker,
                "Headline": title_clean,
                "Catalyst": catalyst,
                "Sentiment": sentiment,
                "Date": datetime.date.today().isoformat(),
                "DateTime": item.get("pubDate", datetime.date.today().isoformat()),
                "Scope": "Stock"
            })
        else:
            matched_news_picks.append({
                "Symbol": "",
                "Ticker": "",
                "Headline": title_clean,
                "Catalyst": catalyst if catalyst != "Corporate Catalyst" else "Market / Macro Catalyst",
                "Sentiment": sentiment,
                "Date": datetime.date.today().isoformat(),
                "DateTime": item.get("pubDate", datetime.date.today().isoformat()),
                "Scope": "Market"
            })
            
    return sort_news_items(matched_news_picks)


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
                # ensure legacy cached entries have expected fields
                if "Type" not in p:
                    p["Type"] = "SELL-BUY" if p.get("Sentiment", "Positive") == "Negative" else "BUY"
                if "Date" not in p:
                    # try to derive a date portion from DateTime or Date
                    p_dt = p.get("DateTime") or p.get("Date") or ""
                    try:
                        import datetime as _dt
                        p["Date"] = _dt.datetime.fromisoformat(str(p_dt)).date().isoformat()
                    except Exception:
                        p["Date"] = str(p_dt)
                cached_map[p["Headline"]] = p

    for news in live_picks:
        headline = news["Headline"]
        if headline in cached_map:
            # Re-use already processed recommendation (delta check)
            picks.append(cached_map[headline])
            continue
            continue

        symbol = news.get("Symbol") or news.get("Ticker") or ""
        scope = news.get("Scope", "Stock")
        sentiment = news.get("Sentiment", "Positive")
        if not symbol:
            picks.append({
                "Ticker": "",
                "Headline": headline,
                "Catalyst": news["Catalyst"],
                "Price": None,
                "Entry Range": "",
                "Stop Loss": "",
                "Target": "",
                "Risk_Reward": "",
                "Sentiment": sentiment,
                "DateTime": news.get("DateTime", news.get("Date", "")),
                "Scope": scope,
            })
            continue

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

        if sentiment == "Negative":
            sl     = round(cmp + 1.2 * atr, 2)
            target = round(cmp - 1.5 * atr, 2)
            rr = "1:1.25 (Short)"
            trade_type = "SELL-BUY"
        else:
            sl     = round(cmp - 1.2 * atr, 2)
            target = round(cmp + 1.5 * atr, 2)
            rr = "1:1.25 (Long)"
            trade_type = "BUY"

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
            "DateTime":    news.get("DateTime", news.get("Date", "")),
            "Date":        news.get("Date", (news.get("DateTime") or "")[:10]),
            "Type":        trade_type,
            "Scope":       scope,
        })

    return sort_news_items(picks)


# ---------------------------------------------------------------------------
# 10-Day News Backtest
# ---------------------------------------------------------------------------
def run_news_backtest(stock_data_dict: dict, historical_events: list | None = None, lookback_days: int = 30, cached_news_items: list | None = None) -> list:
    """
    Evaluates historical news catalyst trades over a configurable lookback window.
    Defaults to a 30-day history view so the news feed can be backtested meaningfully.
    
    Supports BOTH:
    1. Hardcoded historical catalyst events (long-only)
    2. Previously computed news picks from cache (long & short from Type/Price/SL/Target fields)
    """
    results = []
    events = historical_events or HISTORICAL_NEWS_CATALYSTS

    # ── Part A: Backtest hardcoded historical catalysts ──
    for item in events:
        symbol   = item["Symbol"]
        date_str = item["Date"]

        if symbol not in stock_data_dict:
            continue

        df = stock_data_dict[symbol]

        try:
            trigger_idx = df.index.get_indexer([pd.to_datetime(date_str)], method='nearest')[0]
        except Exception:
            continue

        if trigger_idx <= 0 or trigger_idx >= len(df) - 1:
            continue

        if lookback_days and trigger_idx > lookback_days:
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
            "Type":         "BUY",
        })

    # ── Part B: Backtest previously computed news picks from cache ──
    if cached_news_items:
        for item in cached_news_items:
            symbol = item.get("Ticker") or item.get("Symbol") or ""
            if not symbol:
                continue
            # Only backtest items that have actual trade parameters (Price > 0, has Stop Loss & Target)
            price = item.get("Price")
            sl_val = item.get("Stop Loss")
            target_val = item.get("Target")
            if price is None or sl_val is None or target_val is None:
                continue
            try:
                price = float(price)
                sl_val = float(sl_val)
                target_val = float(target_val)
            except (ValueError, TypeError):
                continue
            if price <= 0 or sl_val <= 0 or target_val <= 0:
                continue

            trade_type = item.get("Type", "BUY")
            date_str = str(item.get("Date", "") or item.get("DateTime", "") or "")[:10]
            if not date_str or date_str < "2000-01-01":
                continue

            if symbol not in stock_data_dict:
                continue
            df = stock_data_dict[symbol]

            try:
                trigger_idx = df.index.get_indexer([pd.to_datetime(date_str)], method='nearest')[0]
            except Exception:
                continue

            if trigger_idx <= 0 or trigger_idx >= len(df) - 1:
                continue

            if lookback_days and trigger_idx > lookback_days:
                continue

            N = len(df)
            status = "Active"
            days_held = 0
            exit_price = price
            pnl_pct = 0.0

            if trade_type == "SELL-BUY":
                # Short trade: SL is above entry, target is below entry
                for check_idx in range(trigger_idx + 1, min(trigger_idx + 6, N)):
                    days_held += 1
                    day_high = float(df['High'].iloc[check_idx])
                    day_low = float(df['Low'].iloc[check_idx])

                    if day_high >= sl_val:
                        status = "Stop Loss Hit"
                        exit_price = sl_val
                        pnl_pct = ((price - sl_val) / price) * 100
                        break
                    elif day_low <= target_val:
                        status = "Target Hit"
                        exit_price = target_val
                        pnl_pct = ((price - target_val) / price) * 100
                        break

                if status == "Active":
                    exit_price = float(df['Close'].iloc[min(trigger_idx + 5, N - 1)])
                    pnl_pct = ((price - exit_price) / price) * 100
            else:
                # Long trade: SL is below entry, target is above entry
                for check_idx in range(trigger_idx + 1, min(trigger_idx + 6, N)):
                    days_held += 1
                    day_high = float(df['High'].iloc[check_idx])
                    day_low = float(df['Low'].iloc[check_idx])

                    if day_low <= sl_val:
                        status = "Stop Loss Hit"
                        exit_price = sl_val
                        pnl_pct = ((sl_val - price) / price) * 100
                        break
                    elif day_high >= target_val:
                        status = "Target Hit"
                        exit_price = target_val
                        pnl_pct = ((target_val - price) / price) * 100
                        break

                if status == "Active":
                    exit_price = float(df['Close'].iloc[min(trigger_idx + 5, N - 1)])
                    pnl_pct = ((exit_price - price) / price) * 100

            results.append({
                "Trigger Date": date_str,
                "Ticker":       symbol.replace(".NS", ""),
                "Catalyst":     item.get("Catalyst", "News"),
                "Headline":     item.get("Headline", ""),
                "Entry Price":  round(price, 2),
                "Target":       round(target_val, 2),
                "Stop Loss":    round(sl_val, 2),
                "Current/Exit": round(exit_price, 2),
                "P&L (%)":      round(pnl_pct, 2),
                "Status":       status,
                "Days Held":    days_held,
                "Type":         trade_type,
            })

    return results
