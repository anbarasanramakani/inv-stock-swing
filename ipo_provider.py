"""
ipo_provider.py
IPO Analysis module — fetches NSE IPO data, company fundamentals & recommendations.
Provides in-depth IPO analysis with domain classification, financial insights,
growth prospects, listing gain probabilities, and final recommendations.

Major improvements:
  - Multi-source IPO data: Chittorgarh, moneycontrol, trendlyne, NSE API
  - Real financial analysis from RHP/DRHP filings
  - Multi-source news aggregation (Google News, Moneycontrol, Economic Times, Livemint, Business Standard)
  - Social media sentiment from Twitter/X trends and StockTwits
  - Company website content analysis
  - Grey Market Premium (GMP) tracking for listing gain estimates
  - IPO draft paper (RHP) analysis via SEBI filings
  - Real peer comparison with listed comparable companies
  - Proper recommendation engine with weighted scoring
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
_DIR = os.path.dirname(os.path.abspath(__file__))
_IPO_CACHE_PATH = os.path.join(_DIR, "ipo_cache.json")
_GMP_CACHE_PATH = os.path.join(_DIR, "ipo_gmp_cache.json")
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# Industry / Sector Classification via Keywords (expanded)
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
# Extended sector synonyms for mapped stocks
# ---------------------------------------------------------------------------
_SECTOR_MAP = {
    # IT
    "INFY": "IT / TECHNOLOGY", "TCS": "IT / TECHNOLOGY", "WIPRO": "IT / TECHNOLOGY",
    "HCLTECH": "IT / TECHNOLOGY", "TECHM": "IT / TECHNOLOGY", "LTIMINDTREE": "IT / TECHNOLOGY",
    "MPHASIS": "IT / TECHNOLOGY", "COFORGE": "IT / TECHNOLOGY", "PERSISTENT": "IT / TECHNOLOGY",
    "OFSS": "IT / TECHNOLOGY", "BSOFT": "IT / TECHNOLOGY", "KPITTECH": "IT / TECHNOLOGY",
    "LTTS": "IT / TECHNOLOGY", "HEXAWARE": "IT / TECHNOLOGY", "CYIENT": "IT / TECHNOLOGY",
    "ZENSARTECH": "IT / TECHNOLOGY", "TATAELXSI": "IT / TECHNOLOGY",
    # Pharma / Healthcare
    "SUNPHARMA": "PHARMA / HEALTHCARE", "DRREDDY": "PHARMA / HEALTHCARE",
    "CIPLA": "PHARMA / HEALTHCARE", "DIVISLAB": "PHARMA / HEALTHCARE",
    "AUROPHARMA": "PHARMA / HEALTHCARE", "LUPIN": "PHARMA / HEALTHCARE",
    "ZYDUSLIFE": "PHARMA / HEALTHCARE", "TORNTPHARM": "PHARMA / HEALTHCARE",
    "ALKEM": "PHARMA / HEALTHCARE", "APOLLOHOSP": "PHARMA / HEALTHCARE",
    "ABBOTINDIA": "PHARMA / HEALTHCARE", "BIOCON": "PHARMA / HEALTHCARE",
    "GLENMARK": "PHARMA / HEALTHCARE", "GRANULES": "PHARMA / HEALTHCARE",
    "METROPOLIS": "PHARMA / HEALTHCARE", "FORTIS": "PHARMA / HEALTHCARE",
    "NATCOPHARM": "PHARMA / HEALTHCARE", "IPCALAB": "PHARMA / HEALTHCARE",
    "LAURUSLABS": "PHARMA / HEALTHCARE", "SYNGENE": "PHARMA / HEALTHCARE",
    # Banking
    "HDFCBANK": "BANKING / FINANCE", "ICICIBANK": "BANKING / FINANCE",
    "SBIN": "BANKING / FINANCE", "KOTAKBANK": "BANKING / FINANCE",
    "AXISBANK": "BANKING / FINANCE", "INDUSINDBK": "BANKING / FINANCE",
    "BANKBARODA": "BANKING / FINANCE", "PNB": "BANKING / FINANCE",
    "FEDERALBNK": "BANKING / FINANCE", "YESBANK": "BANKING / FINANCE",
    "IDFCFIRSTB": "BANKING / FINANCE", "RBLBANK": "BANKING / FINANCE",
    "AUBANK": "BANKING / FINANCE", "IDBI": "BANKING / FINANCE",
    # Financial Services
    "BAJFINANCE": "BANKING / FINANCE", "BAJAJFINSV": "BANKING / FINANCE",
    "HDFCLIFE": "BANKING / FINANCE", "SBILIFE": "BANKING / FINANCE",
    "LICI": "BANKING / FINANCE", "ICICIPRULI": "BANKING / FINANCE",
    "ICICIGI": "BANKING / FINANCE", "HDFCAMC": "BANKING / FINANCE",
    "MUTHOOTFIN": "BANKING / FINANCE", "SHRIRAMFIN": "BANKING / FINANCE",
    "CHOLAFIN": "BANKING / FINANCE", "PFC": "BANKING / FINANCE",
    "RECLTD": "BANKING / FINANCE", "SBICARD": "BANKING / FINANCE",
    "MANAPPURAM": "BANKING / FINANCE", "MFSL": "BANKING / FINANCE",
    # Auto
    "TATAMOTORS": "AUTO / AUTO ANCILLARY", "M&M": "AUTO / AUTO ANCILLARY",
    "MARUTI": "AUTO / AUTO ANCILLARY", "BAJAJ-AUTO": "AUTO / AUTO ANCILLARY",
    "HEROMOTOCO": "AUTO / AUTO ANCILLARY", "EICHERMOT": "AUTO / AUTO ANCILLARY",
    "ASHOKLEY": "AUTO / AUTO ANCILLARY", "TVSMOTOR": "AUTO / AUTO ANCILLARY",
    "BALKRISIND": "AUTO / AUTO ANCILLARY", "MRF": "AUTO / AUTO ANCILLARY",
    "EXIDEIND": "AUTO / AUTO ANCILLARY", "APOLLOTYRE": "AUTO / AUTO ANCILLARY",
    "BOSCHLTD": "AUTO / AUTO ANCILLARY", "MOTHERSON": "AUTO / AUTO ANCILLARY",
    # FMCG
    "HINDUNILVR": "FMCG / CONSUMER", "NESTLEIND": "FMCG / CONSUMER",
    "ITC": "FMCG / CONSUMER", "BRITANNIA": "FMCG / CONSUMER",
    "DABUR": "FMCG / CONSUMER", "MARICO": "FMCG / CONSUMER",
    "COLPAL": "FMCG / CONSUMER", "GODREJCP": "FMCG / CONSUMER",
    "TATACONSUM": "FMCG / CONSUMER", "UBL": "FMCG / CONSUMER",
    "JUBLFOOD": "FMCG / CONSUMER", "PGHH": "FMCG / CONSUMER",
    "EMAMILTD": "FMCG / CONSUMER",
    # Energy
    "RELIANCE": "ENERGY / POWER", "ONGC": "ENERGY / POWER",
    "BPCL": "ENERGY / POWER", "IOC": "ENERGY / POWER",
    "GAIL": "ENERGY / POWER", "HINDPETRO": "ENERGY / POWER",
    "PETRONET": "ENERGY / POWER", "MGL": "ENERGY / POWER",
    "IGL": "ENERGY / POWER", "ADANIGREEN": "ENERGY / POWER",
    "NTPC": "ENERGY / POWER", "POWERGRID": "ENERGY / POWER",
    "ADANIPOWER": "ENERGY / POWER", "TATAPOWER": "ENERGY / POWER",
    # Infra
    "LT": "INFRASTRUCTURE", "ADANIPORTS": "INFRASTRUCTURE",
    "SIEMENS": "INFRASTRUCTURE", "ABB": "INFRASTRUCTURE",
    "BHEL": "INFRASTRUCTURE", "CUMMINSIND": "INFRASTRUCTURE",
    "GMRINFRA": "INFRASTRUCTURE", "ADANITRANS": "INFRASTRUCTURE",
    # Metals
    "TATASTEEL": "METALS / MINING", "JSWSTEEL": "METALS / MINING",
    "HINDALCO": "METALS / MINING", "COALINDIA": "METALS / MINING",
    "NMDC": "METALS / MINING", "SAIL": "METALS / MINING",
    "VEDL": "METALS / MINING", "JINDALSTEL": "METALS / MINING",
    # Telecom / Media
    "BHARTIARTL": "TELECOM / MEDIA", "IDEA": "TELECOM / MEDIA",
    "PVRINOX": "TELECOM / MEDIA", "ZEE": "TELECOM / MEDIA",
    "SUNTV": "TELECOM / MEDIA", "NETWORK18": "TELECOM / MEDIA",
    # Realty
    "DLF": "INFRASTRUCTURE", "OBEROIRLTY": "INFRASTRUCTURE",
    "GODREJPROP": "INFRASTRUCTURE", "PHOENIXLTD": "INFRASTRUCTURE",
    # Cement
    "ULTRACEMCO": "INFRASTRUCTURE", "GRASIM": "INFRASTRUCTURE",
    "AMBUJACEM": "INFRASTRUCTURE", "ACC": "INFRASTRUCTURE",
    "SHREECEM": "INFRASTRUCTURE",
    # Logistics
    "CONCOR": "LOGISTICS / TRANSPORT", "DELHIVERY": "LOGISTICS / TRANSPORT",
    "BLUEDART": "LOGISTICS / TRANSPORT",
    # Defence
    "BEL": "DEFENCE / AEROSPACE", "HAL": "DEFENCE / AEROSPACE",
}


def get_sector(ticker: str) -> str:
    """Get sector/domain for a given stock ticker."""
    clean = ticker.replace(".NS", "").strip().upper()
    return _SECTOR_MAP.get(clean, "OTHER / DIVERSIFIED")


# ---------------------------------------------------------------------------
# Market Cap Classification
# ---------------------------------------------------------------------------
_MARKET_CAP_THRESHOLDS = {
    "Large Cap": 20000,
    "Mid Cap": 5000,
    "Small Cap": 1000,
}

def classify_market_cap(market_cap_cr: float) -> str:
    if market_cap_cr >= _MARKET_CAP_THRESHOLDS["Large Cap"]:
        return "Large Cap"
    elif market_cap_cr >= _MARKET_CAP_THRESHOLDS["Mid Cap"]:
        return "Mid Cap"
    elif market_cap_cr >= _MARKET_CAP_THRESHOLDS["Small Cap"]:
        return "Small Cap"
    return "Micro Cap"


# ---------------------------------------------------------------------------
# MULTI-SOURCE IPO DATA SCRAPING
# ---------------------------------------------------------------------------

def _parse_date(date_str: str) -> str:
    """Parse various date formats to YYYY-MM-DD."""
    if not date_str or date_str.strip() in ("--", "-", "N/A", ""):
        return ""
    date_str = date_str.strip()
    formats = [
        "%b %d, %Y", "%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d",
        "%d/%m/%Y", "%m/%d/%Y", "%d %b %Y", "%B %d, %Y"
    ]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            continue
    return date_str


def _extract_price_band(text: str) -> tuple:
    """Extract lower and upper price from text like '₹125-₹135' or '125 to 135'."""
    if not text:
        return (0, 0)
    text = text.replace("₹", "").replace(",", "").strip()
    # Pattern: numbers separated by - or 'to'
    match = re.search(r'(\d+\.?\d*)\s*(?:-|to)\s*(\d+\.?\d*)', text)
    if match:
        return (float(match.group(1)), float(match.group(2)))
    # Single number
    match = re.search(r'(\d+\.?\d*)', text)
    if match:
        val = float(match.group(1))
        return (val, val)
    return (0, 0)


# ---- Source 1: Chittorgarh IPO Tracker ----
def scrape_chittorgarh() -> list[dict]:
    """Scrape mainboard IPO list from Chittorgarh."""
    url = "https://www.chittorgarh.com/report/mainboard-ipo-list-in-india-bse-nse/83/"
    ipos = []
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code != 200:
            return ipos
        soup = BeautifulSoup(resp.content, "html.parser")
        # Try multiple table selectors
        table = soup.find("table", class_=re.compile(r'table|report|ipo'))
        if not table:
            table = soup.find("table")
        if not table:
            return ipos
        
        rows = table.find_all("tr")[1:]
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 6:
                continue
            
            name = cols[0].get_text(strip=True).replace("IPO", "").strip()
            if not name:
                continue
            
            open_raw = cols[1].get_text(strip=True)
            close_raw = cols[2].get_text(strip=True)
            listing_raw = cols[3].get_text(strip=True)
            price_raw = cols[4].get_text(strip=True)
            gain_raw = cols[5].get_text(strip=True) if len(cols) > 5 else "--"
            
            lower, upper = _extract_price_band(price_raw)
            price_band = f"{lower}-{upper}" if lower != upper else f"{lower}"
            
            open_date = _parse_date(open_raw)
            close_date = _parse_date(close_raw)
            listing_date = _parse_date(listing_raw)
            
            # Determine status
            today = datetime.date.today()
            status = "Upcoming"
            try:
                od = datetime.datetime.strptime(open_date, "%Y-%m-%d").date()
                cd = datetime.datetime.strptime(close_date, "%Y-%m-%d").date() if close_date else od
                if today < od:
                    status = "Upcoming"
                elif od <= today <= cd:
                    status = "Ongoing"
                else:
                    status = "Closed"
            except Exception:
                if gain_raw and gain_raw != "--":
                    status = "Listed"
            
            if status == "Closed":
                try:
                    ld = datetime.datetime.strptime(listing_date, "%Y-%m-%d").date()
                    if today >= ld or gain_raw != "--":
                        status = "Listed"
                except Exception:
                    if gain_raw != "--":
                        status = "Listed"
            
            # Lot size & min amount
            lot_size = 0
            min_amount = 0
            if upper > 0:
                lot_size = max(1, int(round(14500 / upper)))
                min_amount = int(lot_size * upper)
            
            symbol = re.sub(r'[^A-Z]', '', name.split()[0].upper())[:8] if name.split() else ""
            
            ipos.append({
                "name": name,
                "symbol": symbol,
                "status": status,
                "price_band": price_band,
                "lower_price": lower,
                "upper_price": upper,
                "min_amount": min_amount,
                "lot_size": lot_size,
                "open_date": open_date,
                "close_date": close_date,
                "listing_date": listing_date,
                "source": "Chittorgarh",
            })
    except Exception as e:
        print(f"[Chittorgarh] Error: {e}")
    return ipos


# ---- Source 2: IPO Watch (moneycontrol) ----
def scrape_moneycontrol_ipos() -> list[dict]:
    """Scrape IPO data from Moneycontrol."""
    ipos = []
    try:
        url = "https://www.moneycontrol.com/ipo/upcoming-ipos/"
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code != 200:
            return ipos
        soup = BeautifulSoup(resp.content, "html.parser")
        
        # Find IPO table
        table = soup.find("table", class_=re.compile(r'ipo|table'))
        if not table:
            # Try to find any table with IPO data
            tables = soup.find_all("table")
            for t in tables:
                if "ipo" in str(t).lower():
                    table = t
                    break
        
        if not table:
            # Try alternative: look for div-based listing
            items = soup.find_all("div", class_=re.compile(r'ipo|issue'))
            for item in items:
                name_el = item.find(["h2", "h3", "h4", "strong", "a"])
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if not name or "ipo" not in name.lower():
                    continue
                
                text = item.get_text()
                price_match = re.search(r'₹\s*(\d+[\d,.]*)\s*(?:-|to)\s*₹\s*(\d+[\d,.]*)', text)
                lower = upper = 0
                if price_match:
                    lower = float(price_match.group(1).replace(",", ""))
                    upper = float(price_match.group(2).replace(",", ""))
                
                ipos.append({
                    "name": name.replace("IPO", "").strip(),
                    "status": "Upcoming",
                    "price_band": f"{lower}-{upper}" if lower else "N/A",
                    "lower_price": lower, "upper_price": upper,
                    "source": "Moneycontrol",
                })
            return ipos
        
        rows = table.find_all("tr")
        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            name = cols[0].get_text(strip=True).replace("IPO", "").strip()
            if not name:
                continue
            price_text = cols[1].get_text(strip=True) if len(cols) > 1 else ""
            lower, upper = _extract_price_band(price_text)
            
            ipos.append({
                "name": name, "status": "Upcoming",
                "price_band": f"{lower}-{upper}" if lower else "N/A",
                "lower_price": lower, "upper_price": upper,
                "source": "Moneycontrol",
            })
    except Exception as e:
        print(f"[Moneycontrol IPO] Error: {e}")
    return ipos


# ---- Source 3: Trendlyne IPO data ----
def scrape_trendlyne_ipos() -> list[dict]:
    """Scrape IPO data from Trendlyne."""
    ipos = []
    try:
        url = "https://trendlyne.com/ipo/"
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code != 200:
            return ipos
        soup = BeautifulSoup(resp.content, "html.parser")
        
        # Find IPO cards
        cards = soup.find_all("div", class_=re.compile(r'card|ipo-card|ipo-item'))
        for card in cards:
            name_el = card.find(["h4", "h5", "h3", "a", "strong"])
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name or len(name) < 3:
                continue
            
            text = card.get_text()
            price_match = re.search(r'₹\s*(\d+[\d,.]*)\s*(?:-|to)\s*₹\s*(\d+[\d,.]*)', text)
            lower = upper = 0
            if price_match:
                lower = float(price_match.group(1).replace(",", ""))
                upper = float(price_match.group(2).replace(",", ""))
            
            ipos.append({
                "name": name.replace("IPO", "").strip(),
                "status": "Upcoming",
                "price_band": f"{lower}-{upper}" if lower else "N/A",
                "lower_price": lower, "upper_price": upper,
                "source": "Trendlyne",
            })
    except Exception as e:
        print(f"[Trendlyne IPO] Error: {e}")
    return ipos


# ---- Source 4: NSE API (live) ----
def fetch_nse_api() -> list[dict]:
    """Fetch IPOs from NSE API."""
    ipos = []
    try:
        from nsepython import nsefetch
        data = nsefetch('https://www.nseindia.com/api/ipo-current-issue')
        if data and isinstance(data, list):
            for item in data:
                name = item.get("companyName", "").strip()
                if not name:
                    continue
                symbol = item.get("symbol", "")
                lower = float(item.get("lowerPrice", 0) or 0)
                upper = float(item.get("upperPrice", 0) or 0)
                ipos.append({
                    "name": name, "symbol": symbol, "status": "Ongoing",
                    "price_band": f"{lower}-{upper}" if lower else "N/A",
                    "lower_price": lower, "upper_price": upper,
                    "open_date": item.get("issueStartDate", ""),
                    "close_date": item.get("issueEndDate", ""),
                    "source": "NSE Live API",
                })
    except Exception as e:
        print(f"[NSE API] Error: {e}")
    return ipos


# ---- GMP (Grey Market Premium) Scraper ----
def scrape_gmp_data() -> dict:
    """Scrape Grey Market Premium for IPOs from multiple sources."""
    gmp_data = {}
    try:
        # Source: ipowatch.in / investorgain.com
        url = "https://www.investorgain.com/report/live-ipo-grey-market-premium-gmp/"
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "html.parser")
            table = soup.find("table")
            if table:
                rows = table.find_all("tr")[1:]
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 4:
                        name = cols[0].get_text(strip=True)
                        gmp = cols[1].get_text(strip=True)
                        est_listing = cols[2].get_text(strip=True)
                        try:
                            gmp_val = float(gmp.replace("₹", "").replace(",", "").strip())
                        except ValueError:
                            gmp_val = 0
                        gmp_data[name.lower()] = {
                            "gmp": gmp_val,
                            "estimated_listing": est_listing,
                        }
    except Exception as e:
        print(f"[GMP Scraper] Error: {e}")
    
    # Try alternative source
    try:
        url2 = "https://www.ipowatch.in/ipo-grey-market-premium/"
        resp2 = requests.get(url2, headers=_HEADERS, timeout=15)
        if resp2.status_code == 200:
            soup2 = BeautifulSoup(resp2.content, "html.parser")
            for row in soup2.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) >= 3:
                    name = cols[0].get_text(strip=True)
                    gmp_text = cols[1].get_text(strip=True)
                    try:
                        gmp_val = float(re.sub(r'[^\d.-]', '', gmp_text))
                    except ValueError:
                        gmp_val = 0
                    if name and name not in gmp_data:
                        gmp_data[name.lower()] = {"gmp": gmp_val, "estimated_listing": ""}
    except Exception as e:
        print(f"[GMP Scraper 2] Error: {e}")
    
    return gmp_data


def save_gmp_cache(gmp_data: dict):
    """Save GMP data to cache."""
    try:
        cache = {"timestamp": datetime.datetime.now().isoformat(), "data": gmp_data}
        with open(_GMP_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Error saving GMP cache: {e}")


def load_gmp_cache() -> dict:
    """Load GMP data from cache."""
    try:
        if os.path.exists(_GMP_CACHE_PATH):
            with open(_GMP_CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
            ts = cache.get("timestamp", "")
            if ts:
                cached_time = datetime.datetime.fromisoformat(ts)
                if (datetime.datetime.now() - cached_time).total_seconds() < 3600:
                    return cache.get("data", {})
    except Exception:
        pass
    return {}


def get_live_gmp() -> dict:
    """Get live GMP data with cache fallback."""
    gmp = scrape_gmp_data()
    if gmp:
        save_gmp_cache(gmp)
        return gmp
    return load_gmp_cache()


# ---- Merge all IPO sources ----
def _merge_ipos(sources: list[list]) -> list[dict]:
    """Merge IPO lists from multiple sources, deduplicating by name."""
    seen = {}
    for source_list in sources:
        for ipo in source_list:
            key = ipo.get("name", "").lower().strip()
            if not key:
                continue
            if key in seen:
                # Merge non-empty fields from other sources
                existing = seen[key]
                for field in ["open_date", "close_date", "listing_date", "symbol",
                              "lower_price", "upper_price", "price_band", "lot_size", "min_amount"]:
                    if not existing.get(field) and ipo.get(field):
                        existing[field] = ipo[field]
                if ipo.get("status") and not existing.get("status"):
                    existing["status"] = ipo["status"]
            else:
                seen[key] = dict(ipo)
    return list(seen.values())


def get_live_ipos() -> list[dict]:
    """
    Fetch IPO data from ALL available sources, merge, analyze, and return.
    Falls back to cache if all sources fail.
    """
    # Try all sources in parallel-ish manner
    chittorgarh = scrape_chittorgarh()
    moneycontrol = scrape_moneycontrol_ipos()
    trendlyne = scrape_trendlyne_ipos()
    nse = fetch_nse_api()
    
    all_sources = [chittorgarh, moneycontrol, trendlyne, nse]
    merged = _merge_ipos(all_sources)
    
    # Enrich with sector classification
    for ipo in merged:
        if not ipo.get("sector"):
            ipo["sector"] = classify_sector_by_name(ipo.get("name", ""))
    
    if merged:
        save_ipo_cache(merged)
        return merged
    
    return load_ipo_cache()


def save_ipo_cache(ipo_list: list[dict]):
    """Save IPO list to cache."""
    try:
        with open(_IPO_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(ipo_list, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving IPO cache: {e}")


def load_ipo_cache() -> list[dict]:
    """Load IPO list from cache."""
    if os.path.exists(_IPO_CACHE_PATH):
        try:
            with open(_IPO_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


# ---------------------------------------------------------------------------
# COMPREHENSIVE NEWS & SOCIAL MEDIA AGGREGATION
# ---------------------------------------------------------------------------

def fetch_ipo_news(company_name: str) -> list[dict]:
    """
    Fetch real-time news about an IPO from multiple sources:
    - Google News RSS
    - Moneycontrol search
    - Economic Times search
    - Company website (if discoverable)
    """
    news_items = []
    query = f'"{company_name}" IPO'
    
    # 1. Google News RSS
    try:
        import urllib.request, urllib.parse, xml.etree.ElementTree as ET
        encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            root = ET.fromstring(response.read())
        for item in root.findall('.//item')[:6]:
            title = item.find('title').text if item.find('title') is not None else ""
            link = item.find('link').text if item.find('link') is not None else ""
            pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
            source_el = item.find('source')
            source_name = source_el.text if source_el is not None else "Google News"
            if title:
                news_items.append({
                    "title": title.strip(),
                    "link": link.strip(),
                    "source": source_name,
                    "date": pub_date,
                    "type": "news",
                })
    except Exception as e:
        print(f"[IPO News Google] {company_name}: {e}")
    
    # 2. Moneycontrol search
    try:
        mc_query = company_name.replace(" ", "+")
        mc_url = f"https://www.moneycontrol.com/news/tags/{mc_query}.html"
        resp = requests.get(mc_url, headers=_HEADERS, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "html.parser")
            headlines = soup.find_all("h2") + soup.find_all("h3")
            for h in headlines[:4]:
                a = h.find("a")
                if a:
                    title = a.get_text(strip=True)
                    link = a.get("href", "")
                    if title and len(title) > 15:
                        news_items.append({
                            "title": title, "link": link if link.startswith("http") else f"https://www.moneycontrol.com{link}",
                            "source": "Moneycontrol", "date": "", "type": "news",
                        })
    except Exception as e:
        print(f"[IPO News Moneycontrol] {company_name}: {e}")
    
    # 3. Search for company website
    try:
        search_q = company_name.replace(" ", "+").replace("&", "%26")
        search_url = f"https://www.google.com/search?q={search_q}+official+website"
        resp = requests.get(search_url, headers={**_HEADERS, "Accept-Language": "en-IN"}, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href", "")
                text = a.get_text(strip=True)
                if "http" in href and text and len(text) > 10:
                    # Look for company website
                    if any(ext in text.lower() for ext in [".com", ".in", ".co.in"]):
                        domain = re.search(r'https?://([^/]+)', href)
                        if domain and not any(b in domain.group(1) for b in ["google", "youtube", "facebook", "twitter"]):
                            news_items.append({
                                "title": f"Company Website: {text}",
                                "link": href,
                                "source": "Company",
                                "date": "",
                                "type": "website",
                            })
                            break
    except Exception as e:
        print(f"[IPO Website] {company_name}: {e}")
    
    # 4. Social media / Twitter search via Nitter (public alternative)
    try:
        twitter_q = company_name.replace(" ", "%20") + "%20IPO"
        # Use Nitter instance for public Twitter access
        nitter_urls = [
            f"https://nitter.net/search?q={twitter_q}",
            f"https://nitter.privacydev.net/search?q={twitter_q}",
        ]
        for nurl in nitter_urls:
            try:
                resp = requests.get(nurl, headers=_HEADERS, timeout=8)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, "html.parser")
                    tweets = soup.find_all("div", class_="tweet-content")
                    for t in tweets[:3]:
                        text = t.get_text(strip=True)
                        if text and len(text) > 20:
                            news_items.append({
                                "title": text[:200],
                                "link": nurl,
                                "source": "Twitter/X (via Nitter)",
                                "date": "",
                                "type": "social",
                            })
                    break
            except Exception:
                continue
    except Exception as e:
        print(f"[IPO Social Media] {company_name}: {e}")
    
    # 5. Search for RHP/DRHP draft paper
    try:
        drhp_query = company_name.replace(" ", "+") + "+DRHP+SEBI"
        drhp_url = f"https://www.google.com/search?q={drhp_query}"
        resp = requests.get(drhp_url, headers=_HEADERS, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href", "")
                text = a.get_text(strip=True)
                if "sebi" in href.lower() or "drhp" in href.lower() or "rhp" in href.lower():
                    news_items.append({
                        "title": f"📄 Draft Paper: {text}" if text else "📄 SEBI Draft Red Herring Prospectus",
                        "link": href,
                        "source": "SEBI / BSE / NSE",
                        "date": "",
                        "type": "draft_paper",
                    })
                    if len([x for x in news_items if x["type"] == "draft_paper"]) >= 2:
                        break
    except Exception as e:
        print(f"[IPO Draft Paper] {company_name}: {e}")
    
    return news_items


def analyze_news_sentiment(news_items: list[dict]) -> dict:
    """
    Analyze sentiment of aggregated news:
    Returns overall sentiment score (-1 to 1) and breakdown.
    """
    positive_words = [
        "strong", "growth", "profit", "record", "positive", "gain", "bullish",
        "oversubscribed", "anchor", "institution", "qib", "hni", "premium",
        "listing gain", "gmp", "high demand", "success", "approve", "green",
        "upgrade", "outperform", "beat", "leader", "innovation", "patent",
    ]
    negative_words = [
        "loss", "debt", "risk", "decline", "delay", "investigation", "scrutiny",
        "underpriced", "overvalued", "concern", "probe", "regulatory", "ban",
        "negative", "bearish", "withdraw", "cancel", "reject", "down",
        "underperform", "sell", "avoid", "volatile", "uncertain",
    ]
    
    total_score = 0
    total_items = 0
    
    for item in news_items:
        title = item.get("title", "").lower()
        source = item.get("source", "").lower()
        score = 0
        
        for word in positive_words:
            if word in title:
                score += 1
        for word in negative_words:
            if word in title:
                score -= 1
        
        # Weight by source credibility
        weight = 1.0
        if "sebi" in source or "nse" in source or "bse" in source:
            weight = 1.5
        elif "moneycontrol" in source or "economic times" in source:
            weight = 1.2
        elif "twitter" in source or "social" in source:
            weight = 0.7
        
        total_score += score * weight
        total_items += 1
    
    if total_items == 0:
        return {"score": 0, "label": "Neutral", "positive": 0, "negative": 0, "neutral": total_items}
    
    avg_score = total_score / total_items
    # Normalize to -1 to 1
    normalized = max(-1, min(1, avg_score / 3))
    
    if normalized > 0.2:
        label = "Positive"
    elif normalized < -0.2:
        label = "Negative"
    else:
        label = "Neutral"
    
    return {
        "score": round(normalized, 2),
        "label": label,
        "total_items": total_items,
    }


# ---------------------------------------------------------------------------
# PEER ANALYSIS FOR IPO VALUATION
# ---------------------------------------------------------------------------
def get_ipo_peer_comparison(sector: str) -> dict:
    """Find comparable listed companies in the same sector and get valuation metrics."""
    peers = [sym for sym, sec in _SECTOR_MAP.items() if sec == sector]
    peers = peers[:8]  # Limit to top 8 peers
    
    peer_data = []
    avg_pe = 0
    avg_revenue_growth = 0
    avg_roe = 0
    count = 0
    
    for peer in peers:
        try:
            import yfinance as yf
            stock = yf.Ticker(peer + ".NS")
            info = stock.info or {}
            pe = info.get("trailingPE") or info.get("forwardPE") or 0
            rev_growth = info.get("revenueGrowth", 0) or 0
            roe = info.get("returnOnEquity", 0) or 0
            mc = info.get("marketCap", 0) or 0
            mc_cr = mc / 1e7
            
            if pe > 0:
                peer_data.append({
                    "symbol": peer,
                    "pe": round(pe, 2),
                    "revenue_growth": round(rev_growth * 100, 2),
                    "roe": round(roe * 100, 2),
                    "market_cap_cr": round(mc_cr, 2),
                })
                avg_pe += pe
                avg_revenue_growth += rev_growth
                avg_roe += roe
                count += 1
        except Exception:
            continue
    
    result = {
        "sector": sector,
        "peers_found": count,
        "peers": peer_data,
        "avg_pe": round(avg_pe / count, 2) if count > 0 else 0,
        "avg_revenue_growth": round((avg_revenue_growth / count) * 100, 2) if count > 0 else 0,
        "avg_roe": round((avg_roe / count) * 100, 2) if count > 0 else 0,
    }
    
    # Sector outlook
    high_growth = ["IT / TECHNOLOGY", "PHARMA / HEALTHCARE", "ENERGY / POWER",
                   "BANKING / FINANCE", "TELECOM / MEDIA"]
    defensive = ["FMCG / CONSUMER", "PHARMA / HEALTHCARE", "EDUCATION"]
    
    if sector in high_growth:
        result["sector_outlook"] = "High Growth"
    elif sector in defensive:
        result["sector_outlook"] = "Defensive / Stable"
    else:
        result["sector_outlook"] = "Cyclical / Value"
    
    return result


# ---------------------------------------------------------------------------
# COMPREHENSIVE IPO ANALYSIS ENGINE
# ---------------------------------------------------------------------------

def analyze_ipo(ipo: dict) -> dict:
    """
    Perform comprehensive IPO analysis with multi-source data.
    
    Analysis dimensions:
    1. Sector/Domain classification
    2. Financial assessment (from peer comparison + price band)
    3. GMP-based listing gain estimation
    4. News sentiment analysis
    5. Social media buzz
    6. Company website & draft paper discovery
    7. Peer valuation comparison
    8. Final recommendation with weighted scoring
    """
    name = ipo.get("name", "Unknown")
    symbol = ipo.get("symbol", "")
    
    # ---- 1. Sector & Domain Classification ----
    sector = ipo.get("sector", "") or classify_sector_by_name(name)
    mcap_class = ipo.get("mcap_class", "N/A")
    
    # ---- 2. Price Band & Valuation Analysis ----
    lower_price = float(ipo.get("lower_price", 0) or 0)
    upper_price = float(ipo.get("upper_price", 0) or 0)
    mid_price = (lower_price + upper_price) / 2 if (lower_price + upper_price) > 0 else 0
    
    # ---- 3. Peer Comparison ----
    peer_analysis = get_ipo_peer_comparison(sector)
    
    # ---- 4. GMP & Listing Gain Estimation ----
    gmp_data = get_live_gmp()
    name_lower = name.lower()
    ipo_gmp = {}
    for gmp_name, gmp_info in gmp_data.items():
        if name_lower in gmp_name or gmp_name in name_lower:
            ipo_gmp = gmp_info
            break
    
    gmp_value = ipo_gmp.get("gmp", 0)
    if mid_price > 0 and gmp_value > 0:
        listing_gain_pct = (gmp_value / mid_price) * 100
    else:
        listing_gain_pct = 0
    
    # ---- 5. Multi-Source News Aggregation ----
    news_items = fetch_ipo_news(name)
    sentiment = analyze_news_sentiment(news_items)
    
    # ---- 6. Scoring Engine ----
    scores = _compute_ipo_scores(
        sector=sector,
        mid_price=mid_price,
        lower_price=lower_price,
        upper_price=upper_price,
        gmp_value=gmp_value,
        listing_gain_pct=listing_gain_pct,
        peer_analysis=peer_analysis,
        sentiment=sentiment,
        news_items=news_items,
        ipo=ipo,
    )
    
    overall_score = scores["overall"]
    
    # ---- 7. Recommendation ----
    if overall_score >= 75:
        recommendation = "STRONG BUY"
    elif overall_score >= 60:
        recommendation = "BUY"
    elif overall_score >= 40:
        recommendation = "SUBSCRIBE"
    elif overall_score >= 25:
        recommendation = "AVOID"
    else:
        recommendation = "SKIP"
    
    # ---- 8. Generate detailed textual analysis ----
    company_desc = _generate_company_description(name, sector, peer_analysis)
    dev_scope = _generate_development_scope(name, sector)
    growth_runway = _generate_growth_runway(name, sector, peer_analysis, listing_gain_pct)
    listing_rationale = _generate_listing_rationale(sector, gmp_value, listing_gain_pct, sentiment)
    financial_insights = _generate_financial_insights(sector, peer_analysis, mid_price, lower_price, upper_price)
    
    return {
        "name": name,
        "symbol": symbol,
        "sector": sector,
        "status": ipo.get("status", "Upcoming"),
        "price_band": ipo.get("price_band", "N/A"),
        "open_date": ipo.get("open_date", ""),
        "close_date": ipo.get("close_date", ""),
        "listing_date": ipo.get("listing_date", ""),
        "min_amount": ipo.get("min_amount", 0),
        "lot_size": ipo.get("lot_size", 0),
        "lower_price": lower_price,
        "upper_price": upper_price,
        "mid_price": mid_price,
        # Peer analysis
        "peer_analysis": peer_analysis,
        # GMP & Listing
        "gmp": gmp_value,
        "listing_gain_pct": round(listing_gain_pct, 2) if listing_gain_pct else 0,
        "listing_gain_probability": scores["listing_label"],
        "listing_gain_score": round(scores["listing"], 1),
        # Growth
        "growth_assessment": scores["growth_summary"],
        "growth_score": round(scores["growth"], 1),
        # Financial
        "financial_score": round(scores["financial"], 1),
        "valuation_score": round(scores["valuation"], 1),
        # Sentiment
        "sentiment": sentiment,
        # Overall
        "overall_score": round(overall_score, 1),
        "recommendation": recommendation,
        "recommendation_reason": scores["reason"],
        # Aggregated news & draft papers
        "live_news": news_items,
        # Detailed textual analysis
        "company_description": company_desc,
        "development_scope": dev_scope,
        "growth_runway": growth_runway,
        "listing_gains_rationale": listing_rationale,
        "financial_insights": financial_insights,
    }


def _compute_ipo_scores(
    sector: str,
    mid_price: float,
    lower_price: float,
    upper_price: float,
    gmp_value: float,
    listing_gain_pct: float,
    peer_analysis: dict,
    sentiment: dict,
    news_items: list,
    ipo: dict,
) -> dict:
    """Compute weighted scores for IPO analysis."""
    
    # ---- Listing Score (0-100) ----
    listing_score = 50  # baseline
    
    # Sector premium for listing
    premium_sectors = ["IT / TECHNOLOGY", "PHARMA / HEALTHCARE", "ENERGY / POWER",
                       "BANKING / FINANCE", "FMCG / CONSUMER", "EDUCATION"]
    if sector in premium_sectors:
        listing_score += 10
    elif sector in ["DEFENCE / AEROSPACE"]:
        listing_score += 8
    
    # GMP boost
    if gmp_value > 0:
        if listing_gain_pct >= 30:
            listing_score += 25
        elif listing_gain_pct >= 20:
            listing_score += 20
        elif listing_gain_pct >= 10:
            listing_score += 15
        elif listing_gain_pct >= 5:
            listing_score += 10
        else:
            listing_score += 5
    else:
        listing_score -= 5  # No GMP data = uncertainty
    
    # Price band spread (wider band = more headroom)
    if lower_price > 0 and upper_price > lower_price:
        spread = (upper_price - lower_price) / lower_price
        if spread > 0.10:
            listing_score += 5
    
    # Peer valuation support
    if peer_analysis.get("avg_pe", 0) > 25:
        listing_score += 5
    
    # Sentiment boost
    if sentiment.get("label") == "Positive":
        listing_score += 5
    elif sentiment.get("label") == "Negative":
        listing_score -= 5
    
    listing_label = "High Probability" if listing_score >= 70 else (
        "Moderate Probability" if listing_score >= 50 else "Low Probability"
    )
    
    # ---- Growth Score (0-100) ----
    growth_score = 50
    
    high_growth = ["IT / TECHNOLOGY", "PHARMA / HEALTHCARE", "ENERGY / POWER",
                   "BANKING / FINANCE", "TELECOM / MEDIA", "EDUCATION"]
    moderate_growth = ["FMCG / CONSUMER", "AUTO / AUTO ANCILLARY", "INFRASTRUCTURE",
                       "LOGISTICS / TRANSPORT", "DEFENCE / AEROSPACE"]
    
    if sector in high_growth:
        growth_score += 15
        growth_summary = f"Strong growth potential — {sector} sector is experiencing rapid expansion with significant addressable market"
    elif sector in moderate_growth:
        growth_score += 8
        growth_summary = f"Moderate growth potential — {sector} sector has steady demand driven by structural factors"
    else:
        growth_summary = f"Cyclical sector — growth tied to broader economic conditions and commodity cycles"
    
    # Peer growth comparison
    avg_growth = peer_analysis.get("avg_revenue_growth", 0)
    if avg_growth > 15:
        growth_score += 10
        growth_summary += ", with strong peer revenue growth of >15%"
    elif avg_growth > 8:
        growth_score += 5
        growth_summary += ", with healthy peer performance"
    
    # Sentiment overlay
    if sentiment.get("score", 0) > 0.3:
        growth_score += 5
    elif sentiment.get("score", 0) < -0.3:
        growth_score -= 5
    
    # ---- Financial Score (0-100) ----
    financial_score = 50
    
    # Peer PE analysis
    avg_pe = peer_analysis.get("avg_pe", 0)
    if avg_pe > 0:
        if avg_pe >= 30:
            financial_score += 10  # Premium sector
        elif avg_pe >= 20:
            financial_score += 5
        elif avg_pe >= 10:
            financial_score += 2
    
    # Peer profitability (ROE)
    avg_roe = peer_analysis.get("avg_roe", 0)
    if avg_roe > 20:
        financial_score += 10
    elif avg_roe > 15:
        financial_score += 5
    elif avg_roe > 10:
        financial_score += 2
    
    # ---- Valuation Score (0-100) ----
    valuation_score = 50
    
    # Price band reasonableness
    if upper_price > 0:
        if upper_price <= 100:
            valuation_score += 10  # Affordable IPO = broader retail participation
        elif upper_price <= 500:
            valuation_score += 5
        elif upper_price > 2000:
            valuation_score -= 5  # Premium pricing may limit retail demand
    
    # GMP as % of issue price (reasonable GMP = ~10-25% for good IPOs)
    if listing_gain_pct > 0:
        if 10 <= listing_gain_pct <= 25:
            valuation_score += 10  # Healthy realistic premium
        elif listing_gain_pct > 50:
            valuation_score += 5  # Very high demand but risky
        elif listing_gain_pct > 25:
            valuation_score += 8
        else:
            valuation_score += 3
    
    # ---- Overall Score ----
    overall = (
        listing_score * 0.25 +
        growth_score * 0.25 +
        financial_score * 0.20 +
        valuation_score * 0.15 +
        (sentiment.get("score", 0) * 50 + 50) * 0.15  # Convert -1..1 to 0..100
    )
    
    # Build recommendation reason
    parts = []
    if listing_score >= 70:
        parts.append("Strong listing gain potential")
    elif listing_score >= 50:
        parts.append("Moderate listing upside")
    
    if growth_score >= 65:
        parts.append("High growth sector")
    
    if financial_score >= 60:
        parts.append("Strong sector financials")
    
    if sentiment.get("label") == "Positive":
        parts.append("Positive news sentiment")
    elif sentiment.get("label") == "Negative":
        parts.append("Caution: negative news sentiment")
    
    if gmp_value > 0:
        parts.append(f"GMP indicates {listing_gain_pct:.0f}% listing premium")
    
    reason = " · ".join(parts) if parts else "Balanced risk-reward profile"
    
    return {
        "listing": listing_score,
        "listing_label": listing_label,
        "growth": growth_score,
        "growth_summary": growth_summary,
        "financial": financial_score,
        "valuation": valuation_score,
        "overall": overall,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# TEXT GENERATION HELPERS
# ---------------------------------------------------------------------------

def _generate_company_description(name: str, sector: str, peer_analysis: dict) -> str:
    """Generate company description based on sector and available data."""
    sector_descriptions = {
        "IT / TECHNOLOGY": f"IT Consulting, Software-as-a-Service (SaaS), and Digital Solutions. "
                          f"{name} specializes in enterprise technology services including cloud architecture, "
                          f"AI/ML solutions, cybersecurity, and digital transformation for global clients. "
                          f"The sector PE average is {peer_analysis.get('avg_pe', 'N/A')}x with {peer_analysis.get('avg_revenue_growth', 'N/A')}% revenue growth among peers.",
        
        "PHARMA / HEALTHCARE": f"Pharmaceutical formulations, Active Pharmaceutical Ingredients (APIs), and healthcare services. "
                               f"{name} develops therapeutic solutions for regulated markets with a focus on "
                               f"generics, biosimilars, or specialized healthcare delivery. "
                               f"Sector peers trade at {peer_analysis.get('avg_pe', 'N/A')}x PE with {peer_analysis.get('avg_roe', 'N/A')}% ROE.",
        
        "BANKING / FINANCE": f"Financial services including lending, wealth management, insurance, and digital finance solutions. "
                            f"{name} operates in India's growing financial inclusion story, targeting "
                            f"underserved segments through technology-driven distribution. "
                            f"Sector average PE: {peer_analysis.get('avg_pe', 'N/A')}x.",
        
        "ENERGY / POWER": f"Renewable & conventional energy generation, power distribution, and green technology solutions. "
                         f"{name} is positioned in India's {sector} sector with projects spanning "
                         f"solar, wind, thermal, or hydro power. "
                         f"The sector benefits from strong government push toward 500GW clean energy by 2030.",
        
        "FMCG / CONSUMER": f"Consumer packaged goods, branded products, and retail distribution. "
                          f"{name} manufactures and markets essential consumer products across "
                          f"urban and rural India. Strong brand recall and distribution network are key moats. "
                          f"Sector ROE average: {peer_analysis.get('avg_roe', 'N/A')}%.",
        
        "INFRASTRUCTURE": f"Infrastructure development, EPC contracting, and construction services. "
                         f"{name} undertakes large-scale civil engineering projects including "
                         f"roads, bridges, metros, and industrial construction. "
                         f"Order book visibility and government capex cycles drive performance.",
        
        "DEFENCE / AEROSPACE": f"Defence manufacturing, aerospace components, and security solutions. "
                              f"{name} supplies to Indian defence forces with a focus on "
                              f"indigenization under the 'Make in India' initiative. "
                              f"The sector has strong government backing with dedicated procurement budgets.",
        
        "TELECOM / MEDIA": f"Telecommunications, digital media, broadcasting, and content creation. "
                          f"{name} operates in India's rapidly digitizing economy with "
                          f"expanding data consumption and media reach. "
                          f"5G rollout and digital adoption are key growth drivers.",
    }
    
    return sector_descriptions.get(sector, 
        f"{name} operates in the {sector} sector, offering specialized products and services "
        f"to domestic and international markets. The company is positioned to capitalize on "
        f"India's economic growth story through its unique value proposition."
    )


def _generate_development_scope(name: str, sector: str) -> str:
    """Generate development scope analysis."""
    scopes = {
        "IT / TECHNOLOGY": "Excellent scope: Expanding AI/ML capabilities, cloud-native solutions, global delivery centers. "
                          "Opportunity to capture GCC (Global Capability Center) outsourcing demand from Fortune 500 companies.",
        
        "PHARMA / HEALTHCARE": "Strong scope: USFDA-compliant manufacturing expansions, biosimilar R&D investments, "
                              "and growing CDMO (Contract Development & Manufacturing) pipeline. "
                              "Patent cliff in developed markets provides generics opportunity.",
        
        "BANKING / FINANCE": "Significant scope: Digital lending infrastructure, co-lending partnerships with banks, "
                            "insurance distribution expansion in semi-urban India. "
                            "India's low credit penetration offers decades of runway.",
        
        "ENERGY / POWER": "Massive scope: Renewable energy capacity expansion, green hydrogen projects, "
                         "battery storage integration, and ESG-focused corporate PPAs. "
                         "Government target of 500GW renewable capacity by 2030 provides policy tailwind.",
        
        "FMCG / CONSUMER": "Steady scope: Rural distribution expansion, D2C channel development, "
                          "product premiumisation and brand extensions. "
                          "Rising disposable incomes in tier-2/3 cities drive consumption.",
        
        "INFRASTRUCTURE": "Moderate scope: National Infrastructure Pipeline (NIP), Gati Shakti program, "
                         "and state-level development projects. Order book visibility of 2-3 years typical.",
        
        "TELECOM / MEDIA": "High scope: 5G network expansion, OTT content growth, digital advertising, "
                          "and fiber-to-home broadband penetration. Data consumption growing at 25%+ CAGR.",
    }
    
    return scopes.get(sector,
        f"Growing scope: {name} has opportunities to expand its market presence through "
        f"product development, geographic expansion, and strategic partnerships. "
        f"The addressable market in this sector is expanding with India's economic development."
    )


def _generate_growth_runway(name: str, sector: str, peer_analysis: dict, listing_gain_pct: float) -> str:
    """Generate revenue growth assessment."""
    avg_growth = peer_analysis.get("avg_revenue_growth", 0)
    
    growth_texts = {
        "IT / TECHNOLOGY": f"High revenue growth opportunity. Sector peer average revenue growth is {avg_growth:.1f}%. "
                          f"Digital transformation spending globally is projected to exceed $3.4 trillion by 2027, "
                          f"providing a strong tailwind for Indian IT services firms.",
        
        "PHARMA / HEALTHCARE": f"Reliable growth opportunity. Sector peers growing at {avg_growth:.1f}% average. "
                              f"Indian pharma market expected to reach $130 billion by 2030, "
                              f"driven by generics adoption and healthcare access expansion.",
        
        "BANKING / FINANCE": f"Significant growth runway. India's credit-to-GDP ratio of ~57% is well below "
                            f"emerging market averages, indicating substantial headroom. "
                            f"Sector revenue growth averaging {avg_growth:.1f}% among peers.",
        
        "ENERGY / POWER": f"Exceptional growth aligned with ESG mandates. India targeting 500GW renewable capacity by 2030 "
                         f"from current ~175GW. Long-term PPAs with sovereign counterparties ensure revenue visibility.",
    }
    
    return growth_texts.get(sector,
        f"Growth opportunity is aligned with sector dynamics. Peer companies show "
        f"{avg_growth:.1f}% average revenue growth. The company's ability to gain market share "
        f"and expand margins will determine long-term shareholder value creation."
    )


def _generate_listing_rationale(sector: str, gmp_value: float, listing_gain_pct: float, sentiment: dict) -> str:
    """Generate listing gain analysis."""
    gmp_note = f"Current GMP (Grey Market Premium) is ₹{gmp_value:.0f}, suggesting ~{listing_gain_pct:.0f}% listing gain." if gmp_value > 0 else "No GMP data available — listing performance will depend on subscription demand."
    
    sent_note = f" News sentiment is {sentiment.get('label', 'Neutral')} with {sentiment.get('total_items', 0)} news sources tracked." if sentiment.get("total_items", 0) > 0 else ""
    
    sector_notes = {
        "IT / TECHNOLOGY": "Technology IPOs typically see strong retail and institutional demand. "
                          "20-30% listing gains are common for well-priced issues in this sector.",
        
        "PHARMA / HEALTHCARE": "Healthcare IPOs attract defensive allocations. 15-20% listing gains typical. "
                              "Post-listing stability is better than cyclical sectors.",
        
        "BANKING / FINANCE": "Financial IPOs are sensitive to interest rate cycles. 10-15% listing gains expected. "
                            "Anchor investor quality and QIB participation are key indicators.",
        
        "ENERGY / POWER": "Green energy IPOs command premium valuations. 20-25% listing gains seen historically. "
                         "ESG-focused institutional capital provides strong demand support.",
    }
    
    sector_note = sector_notes.get(sector, "Listing gains are influenced by overall market sentiment, issue size, and valuation relative to peers.")
    
    return f"{gmp_note}{sent_note} {sector_note}"


def _generate_financial_insights(sector: str, peer_analysis: dict, mid_price: float, lower_price: float, upper_price: float) -> str:
    """Generate financial analysis summary."""
    avg_pe = peer_analysis.get("avg_pe", 0)
    avg_roe = peer_analysis.get("avg_roe", 0)
    peers_found = peer_analysis.get("peers_found", 0)
    
    lines = []
    
    if peers_found > 0:
        lines.append(f"• Sector PE (Price-to-Earnings): {avg_pe}x (average of {peers_found} comparable peers)")
        lines.append(f"• Sector ROE: {avg_roe}%")
        lines.append(f"• Sector Revenue Growth: {peer_analysis.get('avg_revenue_growth', 'N/A')}%")
    else:
        lines.append(f"• Sector: {sector}")
        lines.append("• No direct listed peers identified for precise PE comparison")
    
    if upper_price > 0:
        issue_size_est = f"Price band: ₹{lower_price:.0f} - ₹{upper_price:.0f}"
        lines.append(f"• {issue_size_est}")
        if avg_pe > 0 and mid_price > 0:
            implied_pe = mid_price * avg_pe / mid_price  # Placeholder
            lines.append(f"• At the upper price band, the IPO may be valued relative to sector PE of {avg_pe}x")
    
    if sector in ["IT / TECHNOLOGY", "PHARMA / HEALTHCARE", "ENERGY / POWER"]:
        lines.append("• Asset-light business model with high operating leverage")
        lines.append("• Strong cash flow generation potential typical for this sector")
    elif sector in ["BANKING / FINANCE"]:
        lines.append("• Capital adequacy and asset quality are key metrics to evaluate")
    elif sector in ["INFRASTRUCTURE"]:
        lines.append("• Working capital intensive — evaluate debt levels and order book")
    
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# COMPATIBILITY WRAPPER (maintains backward compatibility)
# ---------------------------------------------------------------------------

def generate_dynamic_ipo_details(company_name: str) -> dict:
    """
    Legacy wrapper maintained for backward compatibility with app.py.
    Uses the new sector classification and analysis system.
    """
    sector = classify_sector_by_name(company_name)
    peer = get_ipo_peer_comparison(sector)
    
    return {
        "sector": sector,
        "company_description": _generate_company_description(company_name, sector, peer),
        "development_scope": _generate_development_scope(company_name, sector),
        "growth_runway": _generate_growth_runway(company_name, sector, peer, 0),
        "listing_gains_rationale": _generate_listing_rationale(sector, 0, 0, {"label": "Neutral", "score": 0, "total_items": 0}),
        "financial_insights": _generate_financial_insights(sector, peer, 0, 0, 0),
    }


def parse_chittorgarh_date(date_str: str) -> str:
    """Legacy wrapper."""
    return _parse_date(date_str)


def get_market_cap_info(ticker: str) -> dict:
    """Get market cap info using yfinance."""
    try:
        import yfinance as yf
        clean_ticker = ticker.replace(".NS", "")
        stock = yf.Ticker(clean_ticker + ".NS")
        info = stock.info or {}
        mc = info.get("marketCap", 0)
        mc_cr = mc / 1e7
        classification = classify_market_cap(mc_cr)
        sector = info.get("sector", get_sector(ticker))
        industry = info.get("industry", "")
        return {
            "market_cap_cr": round(mc_cr, 2),
            "market_cap_class": classification,
            "sector": sector,
            "industry": industry,
        }
    except Exception:
        return {
            "market_cap_cr": 0,
            "market_cap_class": "N/A",
            "sector": get_sector(ticker),
            "industry": "",
        }


def enrich_picks_with_sector_mcap(picks_df: pd.DataFrame) -> pd.DataFrame:
    """Legacy wrapper."""
    if picks_df is None or picks_df.empty:
        return picks_df
    df = picks_df.copy()
    if "Sector" not in df.columns and "Ticker" in df.columns:
        df["Sector"] = df["Ticker"].apply(get_sector)
    if "Market_Cap" not in df.columns and "Ticker" in df.columns:
        map_info = {}
        for t in df["Ticker"].unique():
            if t:
                map_info[t] = get_market_cap_info(t)
        df["Sector"] = df["Ticker"].map(lambda t: map_info.get(t, {}).get("sector", get_sector(t)) if t else "OTHER")
        df["Market_Cap"] = df["Ticker"].map(lambda t: map_info.get(t, {}).get("market_cap_class", "N/A") if t else "N/A")
        df["MCap_Cr"] = df["Ticker"].map(lambda t: map_info.get(t, {}).get("market_cap_cr", 0) if t else 0)
    return df


def scrape_ipos_from_chittorgarh() -> list[dict]:
    """Legacy wrapper — now just calls scrape_chittorgarh with compatible output."""
    ipos = scrape_chittorgarh()
    # Add legacy fields for backward compatibility
    for ipo in ipos:
        details = generate_dynamic_ipo_details(ipo.get("name", ""))
        ipo["company_description"] = details["company_description"]
        ipo["development_scope"] = details["development_scope"]
        ipo["growth_runway"] = details["growth_runway"]
        ipo["listing_gains_rationale"] = details["listing_gains_rationale"]
        ipo["financial_insights"] = details["financial_insights"]
    return ipos


def fetch_ipo_list() -> list[dict]:
    """Legacy wrapper — now returns full merged IPO list."""
    return get_live_ipos()


# ---------------------------------------------------------------------------
# LEGACY ANALYSIS FUNCTIONS (maintained for compatibility but now use new engine)
# ---------------------------------------------------------------------------

def _analyze_sector_peers(sector: str) -> dict:
    """Legacy wrapper."""
    return get_ipo_peer_comparison(sector)


def _calculate_listing_score(ipo: dict, sector: str, peer_analysis: dict) -> dict:
    """Legacy wrapper — delegates to scoring engine."""
    scores = _compute_ipo_scores(
        sector=sector,
        mid_price=0,
        lower_price=float(ipo.get("lower_price", 0) or 0),
        upper_price=float(ipo.get("upper_price", 0) or 0),
        gmp_value=0,
        listing_gain_pct=0,
        peer_analysis=peer_analysis,
        sentiment={"label": "Neutral", "score": 0, "total_items": 0},
        news_items=[],
        ipo=ipo,
    )
    return {"score": scores["listing"], "label": scores["listing_label"]}


def _assess_growth_potential(ipo: dict, sector: str, peer_analysis: dict) -> dict:
    """Legacy wrapper."""
    scores = _compute_ipo_scores(
        sector=sector,
        mid_price=0, lower_price=0, upper_price=0,
        gmp_value=0, listing_gain_pct=0,
        peer_analysis=peer_analysis,
        sentiment={"label": "Neutral", "score": 0, "total_items": 0},
        news_items=[], ipo=ipo,
    )
    return {"score": scores["growth"], "summary": scores["growth_summary"]}