"""
ipo_provider.py
Core IPO Intelligence & Recommendation Engine.
Fuses regulatory prospectus data, exchange subscription multiples,
grey market indicators, and real-time social/news sentiment metrics.
"""
import requests
import json
import datetime
import re
import os
import time
import hashlib
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np

try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False


def _cache_data_decorator(ttl=3600):
    def decorator(fn):
        if _HAS_STREAMLIT:
            return st.cache_data(ttl=ttl)(fn)
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Constants & Configuration
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "."
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ---------------------------------------------------------------------------
# Industry / Sector Classification via Keywords
# ---------------------------------------------------------------------------
def classify_sector_by_name(company_name: str) -> str:
    """Classify company into a sector/domain based on its name and keywords."""
    name_lower = company_name.lower()
    
    sector_keywords = {
        "IT / TECHNOLOGY": [
            "tech", "soft", "digital", "system", "consultancy", "solution", "info",
            "cyber", "data", "cloud", "saas", "software", "comput", "network",
            "semicon", "chip", "electronics", "ai ", "machine learning", "iot",
            "blockchain", "robotic", "automation"
        ],
        "PHARMA / HEALTHCARE": [
            "pharma", "biotech", "life science", "health", "hospital", "clinic",
            "med", "diagnostic", "therapeut", "drug", "vaccine", "bio",
            "surgical", "cardiac", "dental", "wellness", "ayurveda"
        ],
        "BANKING / FINANCE": [
            "bank", "finance", "capital", "wealth", "credit", "invest",
            "insurance", "assurance", "broking", "housing finance", "nbfc",
            "microfin", "lending", "asset management", "mutual fund"
        ],
        "INFRASTRUCTURE": [
            "infra", "construction", "road", "build", "engineer", "project",
            "rail", "metro", "bridge", "tunnel", "cement", "steel struct",
            "realty", "real estate", "property", "developer", "housing"
        ],
        "ENERGY / POWER": [
            "solar", "wind", "green", "renewable", "power", "energy",
            "electric", "utility", "thermal", "hydro", "biomass", "grid"
        ],
        "FMCG / CONSUMER": [
            "food", "beverage", "consumer", "retail", "mart", "milk", "dairy",
            "snack", "packaged", "personal care", "cosmetic", "brand",
            "fashion", "apparel", "textile", "garment"
        ],
        "METALS / MINING": [
            "metal", "steel", "iron", "copper", "aluminum", "mine", "mineral",
            "alloy", "foundry", "forging", "cast"
        ],
        "TELECOM / MEDIA": [
            "telecom", "telecommunication", "broadband", "media", "entertainment",
            "broadcast", "publishing", "advert", "digital media", "ott"
        ],
        "LOGISTICS / TRANSPORT": [
            "logistic", "transport", "shipping", "warehouse", "courier",
            "freight", "supply chain", "cargo", "port", "terminal"
        ],
        "AGRICULTURE / AGRO": [
            "agriculture", "agro", "farm", "fertilizer", "seed", "pesticide",
            "irrigation", "food process", "sugar", "rice", "wheat"
        ],
        "AUTO / AUTO ANCILLARY": [
            "auto", "automotive", "motor", "vehicle", "tyre", "tire",
            "battery", "component", "spare", "ancillar"
        ],
        "HOSPITALITY / TOURISM": [
            "hotel", "hospitality", "resort", "tourism", "travel", "restaurant",
            "leisure", "entertainment"
        ],
        "EDUCATION": [
            "education", "learning", "skill", "training", "coaching",
            "school", "college", "university", "edtech", "e-learning"
        ],
        "DEFENCE / AEROSPACE": [
            "defence", "defense", "aero", "space", "aerospace", "drone",
            "missile", "ammunition", "security"
        ],
    }
    
    for sector, keywords in sector_keywords.items():
        for kw in keywords:
            if kw in name_lower:
                return sector
    
    return "OTHER / DIVERSIFIED"

# ---------------------------------------------------------------------------
# Peer-Group Sector Mapping & Tickers
# ---------------------------------------------------------------------------
_SECTOR_MAP = {
    "INFY": "IT / TECHNOLOGY", "TCS": "IT / TECHNOLOGY", "WIPRO": "IT / TECHNOLOGY",
    "HCLTECH": "IT / TECHNOLOGY", "TECHM": "IT / TECHNOLOGY",
    "SUNPHARMA": "PHARMA / HEALTHCARE", "CIPLA": "PHARMA / HEALTHCARE",
    "DRREDDY": "PHARMA / HEALTHCARE", "DIVISLAB": "PHARMA / HEALTHCARE",
    "HDFCBANK": "BANKING / FINANCE", "ICICIBANK": "BANKING / FINANCE",
    "SBIN": "BANKING / FINANCE", "KOTAKBANK": "BANKING / FINANCE",
    "AXISBANK": "BANKING / FINANCE",
    "BAJFINANCE": "BANKING / FINANCE", "LICI": "BANKING / FINANCE",
    "LT": "INFRASTRUCTURE", "DLF": "INFRASTRUCTURE",
    "ADANIPORTS": "INFRASTRUCTURE", "SIEMENS": "INFRASTRUCTURE",
    "ADANIGREEN": "ENERGY / POWER", "TATAPOWER": "ENERGY / POWER",
    "NTPC": "ENERGY / POWER", "RELIANCE": "ENERGY / POWER",
    "HINDUNILVR": "FMCG / CONSUMER", "NESTLEIND": "FMCG / CONSUMER",
    "ITC": "FMCG / CONSUMER", "BRITANNIA": "FMCG / CONSUMER",
    "TATAMOTORS": "AUTO / AUTO ANCILLARY", "MARUTI": "AUTO / AUTO ANCILLARY",
    "M&M": "AUTO / AUTO ANCILLARY", "BAJAJ-AUTO": "AUTO / AUTO ANCILLARY",
    "TATASTEEL": "METALS / MINING", "JSWSTEEL": "METALS / MINING",
    "HINDALCO": "METALS / MINING",
    "BHARTIARTL": "TELECOM / MEDIA",
    "DELHIVERY": "LOGISTICS / TRANSPORT", "BLUEDART": "LOGISTICS / TRANSPORT",
    "CONCOR": "LOGISTICS / TRANSPORT",
    "BEL": "DEFENCE / AEROSPACE", "HAL": "DEFENCE / AEROSPACE",
    "ULTRACEMCO": "INFRASTRUCTURE", "GRASIM": "INFRASTRUCTURE",
    "PIDILITIND": "CHEMICALS",
    "TRENT": "RETAIL", "TITAN": "RETAIL", "DMART": "RETAIL",
}


def get_sector(ticker: str) -> str:
    """Get sector/domain for a given listed stock ticker."""
    clean = ticker.replace(".NS", "").strip().upper()
    return _SECTOR_MAP.get(clean, "OTHER / DIVERSIFIED")


def get_peer_group_for_sector(sector: str) -> List[str]:
    """Retrieve top listed peers for peer comparison analytics."""
    peers = [sym for sym, sec in _SECTOR_MAP.items() if sec == sector]
    if peers:
        return peers[:8]
    return ["TCS", "INFY", "HCLTECH"]  # default fallback peers


def classify_market_cap(market_cap_cr: float) -> str:
    if market_cap_cr >= 20000:
        return "Large Cap"
    elif market_cap_cr >= 5000:
        return "Mid Cap"
    elif market_cap_cr >= 1000:
        return "Small Cap"
    return "Micro Cap"


# ---------------------------------------------------------------------------
# Helper Date Parsing
# ---------------------------------------------------------------------------
def _parse_date(date_str: str) -> str:
    """Parse unstructured date strings into standardized YYYY-MM-DD format."""
    if not date_str:
        return ""
    date_str = date_str.strip()
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%b %d, %Y", "%Y-%m-%d", "%d %b %Y", "%d %B, %Y"):
        try:
            return datetime.datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    match = re.search(r'(\d{1,2})[-/ ]([A-Za-z]{3})[-/ ](\d{2,4})', date_str)
    if match:
        try:
            d, m, y = match.groups()
            if len(y) == 2:
                y = "20" + y
            return datetime.datetime.strptime(f"{d}-{m}-{y}", "%d-%b-%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return date_str


# ---------------------------------------------------------------------------
# Programmatic Scrapers & Aggregation Engines
# ---------------------------------------------------------------------------

def fetch_sebi_filings(page: int = 1) -> List[Dict]:
    """
    Crawls SEBI's public issues filings page using the internal AJAX gateway.
    Fetches official DRHP/RHP filing dates and document URLs.
    """
    api_url = "https://www.sebi.gov.in/sebiweb/ajax/home/getnewslistinfo.jsp"
    payload = {
        "nextValue": "1", "next": "n", "search": "",
        "fromDate": "", "toDate": "", "fromYear": "", "toYear": "",
        "deptId": "", "sid": "3", "ssid": "-1", "smid": "0",
        "intmid": "-1", "doDirect": str(page)
    }
    
    filings = []
    try:
        r = requests.post(api_url, data=payload, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        rows = soup.select("tr:has(td)")
        
        for tr in rows:
            tds = tr.select("td")
            if len(tds) >= 2:
                date_txt = tds[0].get_text(strip=True)
                anchor = tds[1].find("a")
                if anchor:
                    title = anchor.get_text(strip=True)
                    doc_url = anchor.get("href", "")
                    filings.append({
                        "filing_date": _parse_date(date_txt),
                        "issuer_title": title,
                        "document_url": doc_url,
                        "is_draft": "drhp" in title.lower()
                    })
    except Exception as e:
        print(f"Error harvesting SEBI filings: {e}")
    return filings


def fetch_chittorgarh_ipos() -> List[Dict]:
    """
    Scrapes the master mainboard IPO schedule from Chittorgarh.
    Retrieves core dates, lot sizing, pricing bands, and issue details.
    """
    url = "https://www.chittorgarh.com/report/mainboard-ipo-list-in-india-bse-nse/83/"
    ipos = []
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        tbody = soup.find("tbody")
        
        if tbody:
            for tr in tbody.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) >= 6:
                    company = tds[0].get_text(strip=True)
                    open_d = tds[1].get_text(strip=True)
                    close_d = tds[2].get_text(strip=True)
                    price_b = tds[3].get_text(strip=True)
                    size = tds[4].get_text(strip=True)
                    
                    ipos.append({
                        "company_name": company,
                        "open_date": _parse_date(open_d),
                        "close_date": _parse_date(close_d),
                        "price_band": price_b,
                        "issue_size_cr": float(re.sub(r"[^\d.]", "", size)) if re.sub(r"[^\d.]", "", size) else 0.0,
                        "domain": classify_sector_by_name(company)
                    })
    except Exception as e:
        print(f"Error parsing Chittorgarh list: {e}")
    return ipos


def fetch_investorgain_gmp() -> Dict[str, Any]:
    """
    Parses live Grey Market Premium (GMP) tables from InvestorGain.
    Exposes expected listing yields, Kostak rates, and premiums.
    """
    url = "https://www.investorgain.com/report/ipo-gmp-performance-tracker/377/"
    gmp_matrix = {}
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        table = soup.find("table")
        
        if table:
            for row in table.find_all("tr")[1:]:
                tds = row.find_all("td")
                if len(tds) >= 7:
                    raw_name = tds[0].get_text(strip=True)
                    clean_name = re.sub(r"\s*(SME|MAINBOARD).*", "", raw_name, flags=re.I).strip()
                    gmp_txt = tds[3].get_text(strip=True)
                    price_txt = tds[5].get_text(strip=True)
                    
                    gmp_val = float(re.sub(r"[^\d.-]", "", gmp_txt)) if re.sub(r"[^\d.-]", "", gmp_txt) else 0.0
                    price_val = float(re.sub(r"[^\d.]", "", price_txt)) if re.sub(r"[^\d.]", "", price_txt) else 1.0
                    
                    gmp_matrix[clean_name.lower()] = {
                        "company_name": clean_name,
                        "gmp": gmp_val,
                        "ipo_price": price_val,
                        "listing_yield_pct": (gmp_val / price_val) * 100.0 if price_val > 0 else 0.0
                    }
    except Exception as e:
        print(f"Error scraping InvestorGain GMP tracker: {e}")
    return gmp_matrix


def fetch_google_news_sentiment(company_name: str) -> Dict[str, Any]:
    """
    Aggregates news narratives using Google News RSS.
    Executes a lexicon mapping sentiment ruleset to output a score from -1.0 to 1.0.
    """
    query = f"{company_name} IPO"
    rss_url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    headlines = []
    try:
        r = requests.get(rss_url, headers=_HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "xml")
        items = soup.find_all("item")
        
        for item in items[:10]:
            title = item.find("title").get_text() if item.find("title") else ""
            link = item.find("link").get_text() if item.find("link") else ""
            pub_date = item.find("pubDate").get_text() if item.find("pubDate") else ""
            headlines.append({"title": title, "link": link, "date": pub_date})
        
        # Sentiment logic
        bullish_lexicon = ["strong", "subscribe", "growth", "surges", "gain", "profit", "undervalued", "high demand", "optimistic"]
        bearish_lexicon = ["avoid", "debt", "caution", "overpriced", "expensive", "risk", "worries", "deficit", "scam"]
        
        sum_sentiment = 0.0
        for h in headlines:
            text = h["title"].lower()
            bull_cnt = sum(1 for w in bullish_lexicon if w in text)
            bear_cnt = sum(1 for w in bearish_lexicon if w in text)
            if bull_cnt > bear_cnt:
                sum_sentiment += 1.0
            elif bear_cnt > bull_cnt:
                sum_sentiment -= 1.0
        
        calculated_score = sum_sentiment / len(headlines) if headlines else 0.0
        return {"headlines": headlines, "score": calculated_score}
    except Exception as e:
        return {"headlines": [], "score": 0.0, "error": str(e)}


def fetch_reddit_sentiment(company_name: str) -> Dict[str, Any]:
    """
    Queries Indian market forums on Reddit using standard JSON endpoints.
    Builds real-time sentiment coordinate indices.
    """
    reddit_headers = {"User-Agent": "IPOAnalyticsEngine/1.0.0"}
    query = f"{company_name} IPO"
    url = f"https://www.reddit.com/r/IndianStreetBets/search.json?q={requests.utils.quote(query)}&restrict_sr=1&sort=relevance&limit=10"
    posts = []
    try:
        r = requests.get(url, headers=reddit_headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            for child in data.get("data", {}).get("children", []):
                pdata = child.get("data", {})
                posts.append({
                    "title": pdata.get("title", ""),
                    "score": pdata.get("score", 0),
                    "permalink": f"https://reddit.com{pdata.get('permalink', '')}"
                })
        
        # Sentiment mapping
        bullish_terms = ["subscribe", "apply", "good", "undervalued", "multibagger", "long term", "listing gain"]
        bearish_terms = ["avoid", "overvalued", "skip", "trap", "expensive", "scam", "bad"]
        
        sum_sentiment = 0.0
        for p in posts:
            text = p["title"].lower()
            bull_cnt = sum(1 for w in bullish_terms if w in text)
            bear_cnt = sum(1 for w in bearish_terms if w in text)
            if bull_cnt > bear_cnt:
                sum_sentiment += 1.0
            elif bear_cnt > bull_cnt:
                sum_sentiment -= 1.0
        
        calculated_score = sum_sentiment / len(posts) if posts else 0.0
        return {"posts": posts, "score": calculated_score}
    except Exception as e:
        return {"posts": [], "score": 0.0, "error": str(e)}


def fetch_stocktwits_sentiment(ticker: str) -> Dict[str, Any]:
    """
    Fetches social sentiment feeds directly from Stocktwits public APIs.
    """
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
    messages = []
    try:
        r = requests.get(url, headers=_HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            msgs = data.get("messages", [])
            score_sum = 0
            count = 0
            for m in msgs:
                body = m.get("body", "")
                sent = m.get("sentiment", {})
                sentiment_label = sent.get("basic", "") if sent else None
                messages.append({
                    "body": body,
                    "sentiment": sentiment_label,
                    "user": m.get("user", {}).get("username", "")
                })
                if sentiment_label == "Bullish":
                    score_sum += 1
                    count += 1
                elif sentiment_label == "Bearish":
                    score_sum -= 1
                    count += 1
            calculated_score = score_sum / count if count > 0 else 0.0
            return {"messages": messages, "score": calculated_score}
    except Exception as e:
        pass
    return {"messages": [], "score": 0.0}


# ---------------------------------------------------------------------------
# Scoring and Recommendation Logic
# ---------------------------------------------------------------------------
def calculate_recommendation(
    revenue_cagr: float,
    pat_margin: float,
    qib_multiple: float,
    retail_multiple: float,
    expected_listing_yield: float,
    reddit_score: float,
    news_score: float,
    debt_to_equity: float,
    ofs_percent: float
) -> Dict[str, Any]:
    """
    Executes the multi-scenario analytical ruleset to output 
    weighted scores and structured strategic recommendations.
    """
    # 1. Financial Score (FS - Weight: 40%)
    fs_raw = max(revenue_cagr / 25.0 * 50.0, 0.0) + max(pat_margin / 15.0 * 50.0, 0.0)
    fs = min(fs_raw, 100.0)
    
    # 2. Demand Score (DS - Weight: 40%)
    ds_raw = max(qib_multiple / 10.0 * 50.0, 0.0) + max(retail_multiple / 15.0 * 50.0, 0.0)
    ds = min(ds_raw, 100.0)
    
    # 3. Sentiment Score (SS - Weight: 20%)
    nlp_mapped = ((reddit_score + news_score + 2.0) / 4.0) * 50.0
    ss_raw = max(expected_listing_yield / 30.0 * 50.0, 0.0) + nlp_mapped
    ss = min(ss_raw, 100.0)
    
    # 4. Penalty Multipliers
    if debt_to_equity <= 1.5:
        pm_debt = 1.0
    elif debt_to_equity <= 2.5:
        pm_debt = 0.8
    else:
        pm_debt = 0.5
        
    if ofs_percent <= 50.0:
        pm_ofs = 1.0
    elif ofs_percent <= 80.0:
        pm_ofs = 0.85
    else:
        pm_ofs = 0.60
    
    # Total Score computation
    raw_weighted = (fs * 0.40) + (ds * 0.40) + (ss * 0.20)
    total_score = raw_weighted * pm_debt * pm_ofs
    
    # Decision boundaries
    if total_score >= 75.0 and fs > 60.0 and ds > 50.0 and ss > 50.0 and debt_to_equity < 1.5:
        recommendation = "SUBSCRIBE"
        rationale = "Strong fundamental financials, robust balance sheet, and massive market demand. Suitable for both listing day premium and long-term holding."
    elif total_score >= 50.0 and (expected_listing_yield >= 25.0 or ds > 60.0):
        recommendation = "SUBSCRIBE FOR LISTING GAINS"
        rationale = "Highly speculative momentum play driven by massive subscription bidding and high grey market premium. Recommend exiting fully on listing day."
    else:
        recommendation = "AVOID"
        rationale = "Elevated capital risks due to excessive debt leverage, large venture exit components (OFS), or weak retail and institutional subscription momentum."
    
    return {
        "financial_score": round(fs, 2),
        "demand_score": round(ds, 2),
        "sentiment_score": round(ss, 2),
        "debt_multiplier": pm_debt,
        "ofs_multiplier": pm_ofs,
        "total_score": round(total_score, 2),
        "recommendation": recommendation,
        "rationale": rationale
    }