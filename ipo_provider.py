"""
ipo_provider.py
IPO Analysis module — fetches NSE IPO data, company fundamentals & recommendations.
Provides in-depth IPO analysis with domain classification, financial insights,
growth prospects, listing gain probabilities, and final recommendations.
"""
import requests
import json
import datetime
import re
from typing import Optional
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
# NSE IPO Data Sources
# ---------------------------------------------------------------------------
_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

# Cache file
_IPO_CACHE_PATH = None
import os
_DIR = os.path.dirname(os.path.abspath(__file__))
_IPO_CACHE_PATH = os.path.join(_DIR, "ipo_cache.json")


# ---------------------------------------------------------------------------
# Domain / Sector Classification Map
# ---------------------------------------------------------------------------
_NSE_SECTOR_MAP = {
    # IT / Technology
    "INFY": "IT", "TCS": "IT", "WIPRO": "IT", "HCLTECH": "IT", "TECHM": "IT",
    "LTIMINDTREE": "IT", "MPHASIS": "IT", "COFORGE": "IT", "PERSISTENT": "IT",
    "OFSS": "IT", "BSOFT": "IT", "KPITTECH": "IT", "LTTS": "IT",
    "MINDTREE": "IT", "NIITTECH": "IT", "HEXAWARE": "IT", "CYIENT": "IT",
    "LTI": "IT", "MINDA": "IT",
    # Pharma / Healthcare
    "SUNPHARMA": "PHARMA", "DRREDDY": "PHARMA", "CIPLA": "PHARMA",
    "DIVISLAB": "PHARMA", "AUROPHARMA": "PHARMA", "LUPIN": "PHARMA",
    "ZYDUSLIFE": "PHARMA", "TORNTPHARM": "PHARMA", "ALKEM": "PHARMA",
    "APOLLOHOSP": "HEALTHCARE", "ABBOTINDIA": "PHARMA", "BIOCON": "PHARMA",
    "GLENMARK": "PHARMA", "GRANULES": "PHARMA", "METROPOLIS": "HEALTHCARE",
    "FORTIS": "HEALTHCARE", "NATCOPHARM": "PHARMA", "IPCALAB": "PHARMA",
    "LAURUSLABS": "PHARMA", "SYNGENE": "PHARMA",
    # Banking & Financial Services
    "HDFCBANK": "BANKING", "ICICIBANK": "BANKING", "SBIN": "BANKING",
    "KOTAKBANK": "BANKING", "AXISBANK": "BANKING", "INDUSINDBK": "BANKING",
    "BANKBARODA": "BANKING", "PNB": "BANKING", "FEDERALBNK": "BANKING",
    "YESBANK": "BANKING", "IDFCFIRSTB": "BANKING", "IDBI": "BANKING",
    "RBLBANK": "BANKING", "BANDHANBNK": "BANKING", "AUBANK": "BANKING",
    "BAJFINANCE": "FINANCIAL", "BAJAJFINSV": "FINANCIAL", "HDFCLIFE": "INSURANCE",
    "SBILIFE": "INSURANCE", "LICI": "INSURANCE", "ICICIPRULI": "INSURANCE",
    "ICICIGI": "INSURANCE", "HDFCAMC": "FINANCIAL", "MUTHOOTFIN": "FINANCIAL",
    "SHRIRAMFIN": "FINANCIAL", "CHOLAFIN": "FINANCIAL", "PFC": "FINANCIAL",
    "RECLTD": "FINANCIAL", "L&TFH": "FINANCIAL", "SBICARD": "FINANCIAL",
    "MANAPPURAM": "FINANCIAL", "MFSL": "FINANCIAL",
    # Auto & Auto Ancillaries
    "TATAMOTORS": "AUTO", "M&M": "AUTO", "MARUTI": "AUTO",
    "BAJAJ-AUTO": "AUTO", "HEROMOTOCO": "AUTO", "EICHERMOT": "AUTO",
    "ASHOKLEY": "AUTO", "TVSMOTOR": "AUTO", "BALKRISIND": "AUTO",
    "BOSCHLTD": "AUTO", "MOTHERSON": "AUTO", "APOLLOTYRE": "AUTO",
    "MRF": "AUTO", "EXIDEIND": "AUTO", "ESCORTS": "AUTO",
    # FMCG
    "HINDUNILVR": "FMCG", "NESTLEIND": "FMCG", "ITC": "FMCG",
    "BRITANNIA": "FMCG", "DABUR": "FMCG", "MARICO": "FMCG",
    "COLPAL": "FMCG", "GODREJCP": "FMCG", "TATACONSUM": "FMCG",
    "PGHH": "FMCG", "UBL": "FMCG", "JUBLFOOD": "FMCG",
    "MCDOWELL": "FMCG", "EMAMILTD": "FMCG",
    # Oil & Gas / Energy
    "RELIANCE": "OIL & GAS", "ONGC": "OIL & GAS", "BPCL": "OIL & GAS",
    "IOC": "OIL & GAS", "GAIL": "OIL & GAS", "HINDPETRO": "OIL & GAS",
    "PETRONET": "OIL & GAS", "MGL": "OIL & GAS", "IGL": "OIL & GAS",
    "GSPL": "OIL & GAS", "GUJGASLTD": "OIL & GAS", "ADANIGREEN": "ENERGY",
    # Infrastructure / Engineering / Capital Goods
    "LT": "INFRA", "ADANIPORTS": "INFRA", "SIEMENS": "INFRA",
    "ABB": "INFRA", "BEL": "DEFENCE", "HAL": "DEFENCE",
    "BHEL": "INFRA", "CUMMINSIND": "INFRA", "L&T": "INFRA",
    "KEC": "INFRA", "IRCON": "INFRA", "NCC": "INFRA",
    "GMRINFRA": "INFRA", "ADANITRANS": "INFRA",
    # Metals & Mining
    "TATASTEEL": "METALS", "JSWSTEEL": "METALS", "HINDALCO": "METALS",
    "COALINDIA": "METALS", "NMDC": "METALS", "SAIL": "METALS",
    "JINDALSTEL": "METALS", "NATIONALUM": "METALS", "HINDCOPPER": "METALS",
    "VEDL": "METALS", "MOIL": "METALS",
    # Telecom
    "BHARTIARTL": "TELECOM", "IDEA": "TELECOM", "INDUSTOWER": "TELECOM",
    "TEJASNET": "TELECOM",
    # Power & Utilities
    "NTPC": "POWER", "POWERGRID": "POWER", "NHPC": "POWER",
    "ADANIPOWER": "POWER", "TATAPOWER": "POWER", "JSWENERGY": "POWER",
    "SJVN": "POWER", "TORNTPOWER": "POWER",
    # Real Estate
    "DLF": "REALTY", "OBEROIRLTY": "REALTY", "GODREJPROP": "REALTY",
    "PHOENIXLTD": "REALTY", "PRESTIGE": "REALTY", "SOBHA": "REALTY",
    "BRIGADE": "REALTY", "SUNTECK": "REALTY",
    # Cement
    "ULTRACEMCO": "CEMENT", "GRASIM": "CEMENT", "AMBUJACEM": "CEMENT",
    "ACC": "CEMENT", "DALBHARAT": "CEMENT", "JKCEMENT": "CEMENT",
    "SHREECEM": "CEMENT", "RAMCOCEM": "CEMENT",
    # Chemicals
    "PIDILITIND": "CHEMICALS", "SRF": "CHEMICALS", "UPL": "AGROCHEMICALS",
    "NAVINFLUOR": "CHEMICALS", "DEEPAKNTR": "CHEMICALS",
    "LALPATHLAB": "HEALTHCARE", "COROMANDEL": "AGROCHEMICALS",
    "PIIND": "AGROCHEMICALS", "BAYERCROP": "AGROCHEMICALS",
    "GSFC": "CHEMICALS", "GNFC": "CHEMICALS",
    # Media & Entertainment
    "PVRINOX": "MEDIA", "ZEE": "MEDIA", "NETWORK18": "MEDIA",
    "SUNTV": "MEDIA", "IIFL": "FINANCIAL",
    # Retail
    "TRENT": "RETAIL", "TITAN": "RETAIL", "DMART": "RETAIL",
    "ABFRL": "RETAIL", "PAGEIND": "RETAIL",
    # Logistics & Shipping
    "CONCOR": "LOGISTICS", "DELHIVERY": "LOGISTICS", "BLUEDART": "LOGISTICS",
    "ADANILOG": "LOGISTICS", "GATI": "LOGISTICS", "TCIEXP": "LOGISTICS",
    # Hospitality / Tourism
    "INDHOTEL": "HOSPITALITY", "EIHOTEL": "HOSPITALITY", "LEMONTREE": "HOSPITALITY",
    # Others / Conglomerates
    "ADANIENT": "CONGLOMERATE", "ADANIENT": "CONGLOMERATE",
}

_MARKET_CAP_THRESHOLDS = {
    "Large Cap": 20000,  # ₹20,000+ Cr
    "Mid Cap": 5000,     # ₹5,000 - ₹20,000 Cr
    "Small Cap": 1000,   # ₹1,000 - ₹5,000 Cr
}


def classify_market_cap(market_cap_cr: float) -> str:
    """Classify market cap into Large/Mid/Small/Micro."""
    if market_cap_cr >= _MARKET_CAP_THRESHOLDS["Large Cap"]:
        return "Large Cap"
    elif market_cap_cr >= _MARKET_CAP_THRESHOLDS["Mid Cap"]:
        return "Mid Cap"
    elif market_cap_cr >= _MARKET_CAP_THRESHOLDS["Small Cap"]:
        return "Small Cap"
    else:
        return "Micro Cap"


def get_sector(ticker: str) -> str:
    """Get sector/domain for a given stock ticker."""
    clean = ticker.replace(".NS", "").strip().upper()
    return _NSE_SECTOR_MAP.get(clean, "OTHER")


def get_market_cap_info(ticker: str) -> dict:
    """Get market cap info using yfinance."""
    try:
        import yfinance as yf
        clean_ticker = ticker.replace(".NS", "")
        stock = yf.Ticker(clean_ticker + ".NS")
        info = stock.info or {}
        mc = info.get("marketCap", 0)
        mc_cr = mc / 1e7  # Convert to Crores
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
    """Add sector and market cap columns to picks DataFrame."""
    if picks_df is None or picks_df.empty:
        return picks_df
    
    df = picks_df.copy()
    
    # Add sector column if not present
    if "Sector" not in df.columns and "Ticker" in df.columns:
        df["Sector"] = df["Ticker"].apply(get_sector)
    
    # Add market cap columns if not present
    if "Market_Cap" not in df.columns and "Ticker" in df.columns:
        # Try to get market cap from LTP * shares outstanding
        # Fall back to just sector info
        map_info = {}
        for t in df["Ticker"].unique():
            if t:
                map_info[t] = get_market_cap_info(t)
        
        df["Sector"] = df["Ticker"].map(lambda t: map_info.get(t, {}).get("sector", get_sector(t)) if t else "OTHER")
        df["Market_Cap"] = df["Ticker"].map(lambda t: map_info.get(t, {}).get("market_cap_class", "N/A") if t else "N/A")
        df["MCap_Cr"] = df["Ticker"].map(lambda t: map_info.get(t, {}).get("market_cap_cr", 0) if t else 0)
    
    return df


# ---------------------------------------------------------------------------
# IPO Data Fetching
# ---------------------------------------------------------------------------
def fetch_ipo_list() -> list[dict]:
    """
    Fetches current, upcoming and recently listed IPOs from NSE.
    Returns list of IPO dicts with details.
    """
    ipo_list = []
    
    # Try NSE API for IPOs
    try:
        # NSE IPO market API
        resp = requests.get(
            "https://www.nseindia.com/api/ipo-market",
            headers=_NSE_HEADERS,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("ipo", []):
                ipo_list.append({
                    "name": item.get("companyName", "Unnamed IPO"),
                    "symbol": item.get("symbol", ""),
                    "status": item.get("status", "Upcoming"),
                    "price_band": item.get("priceBand", "N/A"),
                    "min_amount": item.get("minAmount", 0),
                    "open_date": item.get("openDate", ""),
                    "close_date": item.get("closeDate", ""),
                    "lot_size": item.get("lotSize", 0),
                    "listing_date": item.get("listingDate", ""),
                    "source": "NSE API",
                })
    except Exception:
        pass
    
    # If NSE API fails, use fallback data with recent known IPOs
    if not ipo_list:
        ipo_list = _get_fallback_ipo_data()
    
    return ipo_list


def _get_fallback_ipo_data() -> list[dict]:
    """Fallback IPO data when API fails."""
    cache_data = []
    if _IPO_CACHE_PATH and os.path.exists(_IPO_CACHE_PATH):
        try:
            with open(_IPO_CACHE_PATH, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
        except Exception:
            pass
            
    # Seed high-profile recent and upcoming IPOs if cache is empty or missing
    if not cache_data:
        cache_data = [
            {
                "name": "Hyundai Motor India Limited",
                "symbol": "HYUNDAI",
                "status": "Listed",
                "price_band": "1865-1960",
                "min_amount": 13720,
                "open_date": "2024-10-15",
                "close_date": "2024-10-17",
                "lot_size": 7,
                "listing_date": "2024-10-22",
                "source": "Seed Fallback"
            },
            {
                "name": "Swiggy Limited",
                "symbol": "SWIGGY",
                "status": "Listed",
                "price_band": "371-390",
                "min_amount": 14820,
                "open_date": "2024-11-06",
                "close_date": "2024-11-08",
                "lot_size": 38,
                "listing_date": "2024-11-13",
                "source": "Seed Fallback"
            },
            {
                "name": "NTPC Green Energy Limited",
                "symbol": "NTPCGREEN",
                "status": "Listed",
                "price_band": "102-108",
                "min_amount": 14904,
                "open_date": "2024-11-19",
                "close_date": "2024-11-22",
                "lot_size": 138,
                "listing_date": "2024-11-27",
                "source": "Seed Fallback"
            },
            {
                "name": "Niva Bupa Health Insurance Limited",
                "symbol": "NIVABUPA",
                "status": "Ongoing",
                "price_band": "70-74",
                "min_amount": 14800,
                "open_date": "2024-11-07",
                "close_date": "2024-11-11",
                "lot_size": 200,
                "listing_date": "2024-11-14",
                "source": "Seed Fallback"
            },
            {
                "name": "One Mobikwik Systems Limited",
                "symbol": "MOBIKWIK",
                "status": "Upcoming",
                "price_band": "350-375",
                "min_amount": 15000,
                "open_date": "2026-02-15",
                "close_date": "2026-02-18",
                "lot_size": 40,
                "listing_date": "2026-02-23",
                "source": "Seed Fallback"
            },
            {
                "name": "Waaree Energies Limited",
                "symbol": "WAAREEENER",
                "status": "Listed",
                "price_band": "1427-1503",
                "min_amount": 13527,
                "open_date": "2024-10-21",
                "close_date": "2024-10-23",
                "lot_size": 9,
                "listing_date": "2024-10-28",
                "source": "Seed Fallback"
            },
            {
                "name": "Ola Electric Mobility Limited",
                "symbol": "OLAELEC",
                "status": "Listed",
                "price_band": "72-76",
                "min_amount": 14820,
                "open_date": "2024-08-02",
                "close_date": "2024-08-06",
                "lot_size": 195,
                "listing_date": "2024-08-09",
                "source": "Seed Fallback"
            }
        ]
        save_ipo_cache(cache_data)
        
    return cache_data


def save_ipo_cache(ipo_list: list[dict]):
    """Save IPO list to cache."""
    if _IPO_CACHE_PATH:
        try:
            with open(_IPO_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(ipo_list, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving IPO cache: {e}")


def load_ipo_cache() -> list[dict]:
    """Load IPO list from cache."""
    if _IPO_CACHE_PATH and os.path.exists(_IPO_CACHE_PATH):
        try:
            with open(_IPO_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def get_live_ipos() -> list[dict]:
    """Get live IPO data, falling back to cache."""
    live = fetch_ipo_list()
    if live:
        save_ipo_cache(live)
        return live
    return load_ipo_cache()


# ---------------------------------------------------------------------------
# IPO Analysis Engine
# ---------------------------------------------------------------------------
def analyze_ipo(ipo: dict) -> dict:
    """
    Perform comprehensive IPO analysis.
    Returns analysis with financial insights, domain assessment, and recommendation.
    """
    name = ipo.get("name", "Unknown")
    symbol = ipo.get("symbol", "")
    
    # Domain / Sector analysis
    sector = "N/A"
    if symbol:
        sector = get_sector(symbol)
    
    # Price band analysis
    price_band = ipo.get("price_band", "N/A")
    min_amount = ipo.get("min_amount", 0)
    lot_size = ipo.get("lot_size", 0)
    
    # Estimate financial metrics using yfinance (if similar listed peers exist)
    peer_analysis = {}
    if sector != "N/A" and sector != "OTHER":
        peer_analysis = _analyze_sector_peers(sector)
    
    # Listing gain probability
    listing_score = _calculate_listing_score(ipo, sector, peer_analysis)
    
    # Revenue growth opportunity assessment
    growth_assessment = _assess_growth_potential(ipo, sector, peer_analysis)
    
    # Overall rating
    overall_score = (listing_score["score"] + growth_assessment["score"]) / 2
    
    # Recommendation
    if overall_score >= 75:
        recommendation = "STRONG BUY"
        recommendation_reason = "Strong fundamentals with high listing gain potential"
    elif overall_score >= 60:
        recommendation = "BUY"
        recommendation_reason = "Good prospects with reasonable valuation"
    elif overall_score >= 40:
        recommendation = "HOLD / SUBSCRIBE"
        recommendation_reason = "Fair opportunity, moderate upside potential"
    elif overall_score >= 25:
        recommendation = "AVOID"
        recommendation_reason = "Risky with limited upside"
    else:
        recommendation = "SKIP"
        recommendation_reason = "Unfavorable risk-reward profile"
    
    return {
        "name": name,
        "symbol": symbol,
        "sector": sector,
        "status": ipo.get("status", "Upcoming"),
        "price_band": price_band,
        "open_date": ipo.get("open_date", ""),
        "close_date": ipo.get("close_date", ""),
        "listing_date": ipo.get("listing_date", ""),
        "min_amount": min_amount,
        "lot_size": lot_size,
        "peer_analysis": peer_analysis,
        "listing_gain_probability": listing_score["label"],
        "listing_gain_score": round(listing_score["score"], 1),
        "growth_assessment": growth_assessment["summary"],
        "growth_score": round(growth_assessment["score"], 1),
        "overall_score": round(overall_score, 1),
        "recommendation": recommendation,
        "recommendation_reason": recommendation_reason,
    }


@_cache_data_decorator(ttl=86400)
def _analyze_sector_peers(sector: str) -> dict:
    """Analyze sector peers for valuation comparison."""
    # Find peer stocks in the same sector
    peers = [sym for sym, sec in _NSE_SECTOR_MAP.items() if sec == sector][:5]
    
    avg_pe = 0
    avg_revenue_growth = 0
    count = 0
    
    for peer in peers:
        try:
            import yfinance as yf
            stock = yf.Ticker(peer + ".NS")
            info = stock.info or {}
            pe = info.get("trailingPE", 0) or info.get("forwardPE", 0)
            rev_growth = info.get("revenueGrowth", 0)
            if pe and pe > 0:
                avg_pe += pe
                count += 1
            if rev_growth:
                avg_revenue_growth += rev_growth
        except Exception:
            continue
    
    sector_peers = {
        "sector": sector,
        "peers_found": count,
        "avg_pe": round(avg_pe / count, 2) if count > 0 else 0,
        "avg_revenue_growth": round((avg_revenue_growth / count) * 100, 2) if count > 0 else 0,
    }
    
    # Add sector assessment
    high_growth_sectors = ["IT", "PHARMA", "HEALTHCARE", "FINANCIAL", "RETAIL", "TELECOM"]
    defensive_sectors = ["FMCG", "PHARMA", "HEALTHCARE", "POWER"]
    
    if sector in high_growth_sectors:
        sector_peers["sector_outlook"] = "High Growth"
    elif sector in defensive_sectors:
        sector_peers["sector_outlook"] = "Defensive / Stable"
    else:
        sector_peers["sector_outlook"] = "Cyclical"
    
    return sector_peers


def _calculate_listing_score(ipo: dict, sector: str, peer_analysis: dict) -> dict:
    """Calculate listing gain probability score (0-100)."""
    score = 50  # Baseline
    
    # Sector premium
    premium_sectors = ["IT", "PHARMA", "HEALTHCARE", "FINANCIAL", "RETAIL"]
    if sector in premium_sectors:
        score += 10
    elif sector in ["FMCG", "DEFENCE"]:
        score += 5
    
    # Price band (lower band = more headroom for listing gains)
    price_band_str = ipo.get("price_band", "0-0")
    try:
        parts = price_band_str.split("-")
        if len(parts) == 2:
            lower = float(parts[0])
            upper = float(parts[1])
            if upper > lower:
                discount = (upper - lower) / lower
                if discount > 0.10:  # >10% band = room for gains
                    score += 5
    except Exception:
        pass
    
    # Peer comparison boost
    if peer_analysis.get("avg_pe", 0) > 20:
        score += 5  # Sector supports premium valuation
    
    # Determine label
    if score >= 70:
        label = "High Probability"
    elif score >= 50:
        label = "Moderate Probability"
    else:
        label = "Low Probability"
    
    return {"score": score, "label": label}


def _assess_growth_potential(ipo: dict, sector: str, peer_analysis: dict) -> dict:
    """Assess revenue growth and development potential."""
    score = 50  # Baseline
    
    # Sector-based growth assessment  
    high_growth = ["IT", "PHARMA", "HEALTHCARE", "FINANCIAL", "RETAIL", "TELECOM", "ENERGY"]
    moderate_growth = ["AUTO", "FMCG", "INFRA", "CHEMICALS", "CEMENT"]
    
    if sector in high_growth:
        score += 15
        summary = f"Strong growth potential — {sector} sector is experiencing rapid expansion"
    elif sector in moderate_growth:
        score += 8
        summary = f"Moderate growth potential — {sector} sector has steady demand"
    else:
        summary = f"Cyclical sector — growth tied to economic conditions"
    
    # Peer growth comparison
    avg_growth = peer_analysis.get("avg_revenue_growth", 0)
    if avg_growth > 15:
        score += 10
        summary += " with strong peer revenue growth"
    elif avg_growth > 8:
        score += 5
        summary += " with healthy peer performance"
    
    return {"score": score, "summary": summary}