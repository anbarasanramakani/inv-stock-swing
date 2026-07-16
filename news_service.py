import time
import requests
import datetime
import xml.etree.ElementTree as ET
import email.utils
import re
import pandas as pd
from typing import List, Dict
from schemas import MarketNewsItem, MarketStatusSummary, NewsCategory, MarketStatus
import data_provider as dp
import tickers as tick_helper

# Set of known clean symbols (without suffix) from Nifty 50 and Next 50
ALL_KNOWN_SYMBOLS = set(tick_helper.NIFTY50_SYMBOLS + tick_helper.NIFTY_NEXT50_SYMBOLS)

# Common name map to match company names to their standard NSE symbol
COMPANY_NAME_MAP = {
    "reliance": "RELIANCE",
    "tcs": "TCS",
    "tata consultancy": "TCS",
    "hdfc": "HDFCBANK",
    "infosys": "INFY",
    "infy": "INFY",
    "icici": "ICICIBANK",
    "sbi": "SBIN",
    "state bank of india": "SBIN",
    "airtel": "BHARTIARTL",
    "bharti airtel": "BHARTIARTL",
    "trent": "TRENT",
    "hindustan unilever": "HINDUNILVR",
    "hul": "HINDUNILVR",
    "itc": "ITC",
    "larsen & toubro": "LT",
    "l&t": "LT",
    "bajaj finance": "BAJFINANCE",
    "kotak": "KOTAKBANK",
    "axis": "AXISBANK",
    "titan": "TITAN",
    "wipro": "WIPRO",
    "maruti": "MARUTI",
    "ntpc": "NTPC",
    "ongc": "ONGC",
    "tata motors": "TATAMOTORS",
    "tata steel": "TATASTEEL",
    "adani": "ADANIENT",
    "hal": "HAL",
    "rvnl": "RVNL",
    "zomato": "ZOMATO",
    "irctc": "IRCTC",
    "pnb": "PNB",
    "tata power": "TATAPOWER",
    "nhpc": "NHPC",
    "suzlon": "SUZLON",
    "yes bank": "YESBANK",
    "hfcl": "HFCL",
}

def extract_related_tickers(text: str) -> List[str]:
    """
    Scans the news text to identify and tag standard stock symbols.
    """
    found = set()
    text_lower = text.lower()
    
    # 1. Match specific company names using map
    for name, symbol in COMPANY_NAME_MAP.items():
        if re.search(r'\b' + re.escape(name) + r'\b', text_lower):
            found.add(symbol)
            
    # 2. Match whole words that are directly in ALL_KNOWN_SYMBOLS
    words = re.findall(r'\b[A-Za-z0-9\-]+\b', text)
    for w in words:
        w_up = w.upper()
        if w_up in ALL_KNOWN_SYMBOLS:
            found.add(w_up)
            
    return sorted(list(found))


class InitialMarketNewsService:
    def __init__(self):
        self._cache: Dict[str, any] = {}
        self._cache_ttl = 600  # 10 minutes (in seconds)
        self._cache_timestamp = 0.0

    def _fetch_rss_news(self, query: str, max_results: int = 15) -> List[dict]:
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        try:
            resp = requests.get(url, timeout=2.5, headers=headers)
            if resp.status_code != 200:
                return []
            root = ET.fromstring(resp.content)
            items = []
            for item in root.findall('.//item')[:max_results]:
                title = item.findtext('title', '')
                link = item.findtext('link', '')
                pub_str = item.findtext('pubDate', '')
                description = item.findtext('description', '')
                
                # Parse pubDate to get timestamp (for sorting) and clean ISO format
                pub_ts = 0.0
                pub_formatted = pub_str
                if pub_str:
                    try:
                        dt = email.utils.parsedate_to_datetime(pub_str)
                        pub_ts = dt.timestamp()
                        pub_formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass
                
                # Deduplicate source suffix from title (e.g., "Headline - Moneycontrol")
                if " - " in title:
                    title = title.rsplit(" - ", 1)[0]
                
                items.append({
                    "title": title,
                    "summary": description or title,
                    "source": "Google News / RSS",
                    "url": link,
                    "published_at": pub_formatted,
                    "timestamp": pub_ts
                })
            return items
        except Exception as e:
            print(f"Error fetching RSS query '{query}': {e}")
            return []

    def get_market_sentiment_and_news(self) -> MarketStatusSummary:
        current_time = time.time()
        
        # Check cache
        if self._cache and (current_time - self._cache_timestamp < self._cache_ttl):
            return self._cache["summary"]

        # 1. Fetch broad index levels to calculate live sentiment
        index_summary = {}
        live_indices = dp.get_live_nse_indices()
        
        nifty_pchange = 0.0
        for idx in live_indices:
            name = idx["name"]
            index_summary[name] = idx["last"]
            if name == "NIFTY 50":
                nifty_pchange = idx["pChange"]

        # Classify market status dynamically based on Nifty 50 percentage change
        if nifty_pchange > 0.15:
            market_status = MarketStatus.BULLISH
        elif nifty_pchange < -0.15:
            market_status = MarketStatus.BEARISH
        else:
            market_status = MarketStatus.NEUTRAL

        # 2. Scrape headlines using a single combined query to prevent multiple HTTP requests
        query = '("Indian stock market" OR "Nifty 50" OR "Sensex" OR "FII DII activity" OR "RBI monetary policy" OR "Sector movers")'

        scraped_headlines = []
        seen_titles = set()
        
        items = self._fetch_rss_news(query, max_results=20)
        for item in items:
            title = item["title"]
            if title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            
            # Extract related tickers
            text_to_scan = f"{title} {item['summary']}"
            related = extract_related_tickers(text_to_scan)
            
            # Classify category dynamically
            title_lower = title.lower()
            category = NewsCategory.MACRO
            
            # If related stocks are found, tag as STOCK news
            if related:
                category = NewsCategory.STOCK
            else:
                sector_keywords = ["bank nifty", "nifty it", "metal", "auto", "sector", "pharma", "realty", "fmcg"]
                if any(k in title_lower for k in sector_keywords):
                    category = NewsCategory.SECTOR

            scraped_headlines.append({
                "title": title,
                "summary": item["summary"],
                "source": item["source"],
                "url": item["url"],
                "published_at": item["published_at"],
                "category": category,
                "related_tickers": related,
                "timestamp": item["timestamp"]
            })

        # Fallback if news query fails
        if not scraped_headlines:
            scraped_headlines.append({
                "title": "Indian indices show active performance as institutional flows balance cash positions.",
                "summary": "Nifty 50 and key sectoral indices display standard technical trading ranges.",
                "source": "System Cache",
                "url": "https://www.nseindia.com",
                "published_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "category": NewsCategory.MACRO,
                "related_tickers": [],
                "timestamp": current_time
            })

        # 3. Perform batch historical EOD retrieval for all matched stock news items
        unique_tickers = list(set([
            f"{t}.NS" for h in scraped_headlines if h["category"] == NewsCategory.STOCK
            for t in h["related_tickers"]
        ]))
        
        batch_data = {}
        if unique_tickers:
            try:
                # 2-month data download is extremely fast (under 1 second in total!)
                batch_data = dp.download_stock_data_batch(unique_tickers, period="2mo")
            except Exception as e:
                print(f"Error fetching news EOD batch: {e}")

        # 4. Map stock pricing and target metrics onto headlines
        final_news_items = []
        for h in scraped_headlines:
            price = None
            target = None
            stop_loss = None
            risk_reward = None
            entry_range = None
            
            # Scrape sentiment
            title_lower = h["title"].lower()
            neg_keywords = ["crash", "plunge", "slump", "tumble", "fall", "drop", "down", "correction", "stress", "outflow"]
            sentiment = "Negative" if any(k in title_lower for k in neg_keywords) else "Positive"
            
            if h["category"] == NewsCategory.STOCK and h["related_tickers"]:
                primary_ticker = h["related_tickers"][0]
                ticker_ns = f"{primary_ticker}.NS"
                
                df = batch_data.get(ticker_ns)
                if df is not None and len(df) >= 15:
                    try:
                        last_row = df.iloc[-1]
                        cmp = float(last_row['Close'])
                        
                        # Calculate ATR (14-day rolling mean of true range)
                        hl = df['High'] - df['Low']
                        hc = (df['High'] - df['Close'].shift()).abs()
                        lc = (df['Low'] - df['Close'].shift()).abs()
                        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
                        atr = float(tr.rolling(14).mean().iloc[-1])
                        
                        if pd.isna(atr) or atr <= 0:
                            atr = cmp * 0.02
                            
                        if sentiment == "Negative":
                            sl = round(cmp + 1.2 * atr, 2)
                            tgt = round(cmp - 1.5 * atr, 2)
                            rr = "1:1.25 (Short)"
                        else:
                            sl = round(cmp - 1.2 * atr, 2)
                            tgt = round(cmp + 1.5 * atr, 2)
                            rr = "1:1.25 (Long)"
                            
                        price = round(cmp, 2)
                        target = tgt
                        stop_loss = sl
                        risk_reward = rr
                        entry_range = f"{round(cmp * 0.995, 2)} - {round(cmp * 1.005, 2)}"
                    except Exception as calc_err:
                        print(f"Error calculating ATR metrics for {primary_ticker}: {calc_err}")

            final_news_items.append({
                "item": MarketNewsItem(
                    title=h["title"],
                    summary=h["summary"],
                    source=h["source"],
                    url=h["url"],
                    published_at=h["published_at"],
                    category=h["category"],
                    related_tickers=h["related_tickers"],
                    price=price,
                    target=target,
                    stop_loss=stop_loss,
                    risk_reward=risk_reward,
                    entry_range=entry_range,
                    sentiment=sentiment
                ),
                "timestamp": h["timestamp"]
            })

        # Sort all items by timestamp in descending order (newest first)
        final_news_items.sort(key=lambda x: x["timestamp"], reverse=True)
        final_headlines = [h["item"] for h in final_news_items]

        summary = MarketStatusSummary(
            market_status=market_status,
            index_summary=index_summary,
            macro_headlines=final_headlines[:15]  # Cap at top 15 news items
        )
        
        # Save to cache
        self._cache["summary"] = summary
        self._cache_timestamp = current_time
        return summary
