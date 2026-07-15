"""
NSE Pulse — Professional Trading Terminal
app.py  (fully self-contained; all helper modules imported from same directory)
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import threading
from plotly.subplots import make_subplots
import datetime, os, time, json


# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG  (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NSE Pulse — Trading Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS  — Premium trading terminal theme
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ─── FORD DESIGN SYSTEM — NSE Pulse Trading Terminal ─── */

/* Base & Reset */
html, body, .stApp {
    background: #05080f !important;
    color: #dde5f0 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}
* { box-sizing: border-box; }
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #08111e; }
::-webkit-scrollbar-thumb { background: #1a2f4a; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #0066cc; }

/* Hide Streamlit chrome */
#MainMenu, footer, .stDeployButton, header[data-testid="stHeader"] { display: none !important; }

/* ── Ford Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #070e1a 0%, #040a12 100%) !important;
    border-right: 1px solid #0d1f35 !important;
}
section[data-testid="stSidebar"] * { color: #c8d8ea !important; }
section[data-testid="stSidebar"] label {
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: #5a7a9a !important;
}
div[data-testid="stSelectbox"] > div > div,
div[data-testid="stNumberInput"] input,
div[data-testid="stTextArea"] textarea {
    background: #08111e !important;
    border: 1px solid #0d1f35 !important;
    border-radius: 6px !important;
    color: #dde5f0 !important;
    font-size: 0.82rem !important;
}
div[data-testid="stSelectbox"] > div > div:focus-within,
div[data-testid="stNumberInput"] input:focus {
    border-color: #0066cc !important;
    box-shadow: 0 0 0 3px rgba(0,102,204,0.18) !important;
}

/* ── Ford Primary Button ── */
div.stButton > button {
    background: linear-gradient(135deg, #003f8a 0%, #0066cc 60%, #0080ff 100%) !important;
    color: #fff !important;
    font-weight: 800 !important;
    font-size: 0.84rem !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 12px 0 !important;
    width: 100% !important;
    box-shadow: 0 4px 24px rgba(0,102,204,0.4), 0 0 0 1px rgba(0,102,204,0.15) !important;
    transition: all 0.22s cubic-bezier(0.4,0,0.2,1) !important;
    cursor: pointer !important;
    position: relative !important;
    overflow: hidden !important;
}
div.stButton > button::after {
    content: '';
    position: absolute; inset: 0;
    background: linear-gradient(135deg, rgba(255,255,255,0.08) 0%, transparent 100%);
    pointer-events: none;
}
div.stButton > button:hover {
    background: linear-gradient(135deg, #0055b3 0%, #0080ff 60%, #33aaff 100%) !important;
    box-shadow: 0 6px 32px rgba(0,128,255,0.55), 0 0 0 1px rgba(0,128,255,0.25) !important;
    transform: translateY(-2px) !important;
}
div.stButton > button:active { transform: translateY(0) !important; }

/* ── Ford Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 2px solid #0d1f35 !important;
    gap: 0 !important; padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #5a7a9a !important;
    font-size: 0.75rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.07em !important;
    text-transform: uppercase !important;
    padding: 11px 22px !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.18s !important;
    margin-bottom: -2px !important;
}
.stTabs [data-baseweb="tab"]:hover { color: #c8d8ea !important; }
.stTabs [aria-selected="true"] {
    color: #0080ff !important;
    border-bottom: 2px solid #0066cc !important;
    background: rgba(0,102,204,0.07) !important;
}
.stTabs [data-baseweb="tab-panel"] { padding: 22px 0 0 !important; }

/* ── Ford Metrics / KPI Tiles ── */
div[data-testid="stMetric"] {
    background: #08111e !important;
    border: 1px solid #0d1f35 !important;
    border-left: 3px solid #0066cc !important;
    border-radius: 8px !important;
    padding: 14px 18px !important;
    transition: border-color 0.2s !important;
}
div[data-testid="stMetric"]:hover { border-left-color: #0080ff !important; }
div[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', 'Courier New', monospace !important;
    font-size: 1.38rem !important;
    font-weight: 700 !important;
    color: #f0f6ff !important;
}
div[data-testid="stMetricLabel"] {
    font-size: 0.66rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: #5a7a9a !important;
}
div[data-testid="stMetricDelta"] svg { display:none !important; }
div[data-testid="stMetricDelta"] > div {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
}

/* ── Ford DataFrame ── */
.stDataFrame { border-radius: 8px !important; overflow: hidden !important;
    border: 1px solid #0d1f35 !important; }
.stDataFrame thead tr th {
    background: #08111e !important;
    color: #5a7a9a !important;
    font-size: 0.68rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.09em !important;
    font-weight: 700 !important;
    border-bottom: 2px solid #0d1f35 !important;
    padding: 10px 14px !important;
}
.stDataFrame tbody tr td {
    background: #05080f !important;
    font-size: 0.8rem !important;
    border-bottom: 1px solid #08111e !important;
    padding: 9px 14px !important;
    color: #c8d8ea !important;
}
.stDataFrame tbody tr:hover td {
    background: #08111e !important;
    color: #f0f6ff !important;
}

/* ── Slider ── */
div[data-testid="stSlider"] > div { color: #c8d8ea !important; }

/* ── Progress ── */
div[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #0066cc, #0080ff) !important;
    border-radius: 4px !important;
}

/* ── Ford Live Pulse ── */
@keyframes ford-pulse {
    0%, 100% { opacity:1; box-shadow: 0 0 0 0 rgba(0,200,83,.6); }
    50% { opacity:0.7; box-shadow: 0 0 0 6px rgba(0,200,83,0); }
}
.live-dot {
    display: inline-block; width: 8px; height: 8px;
    background: #00c853; border-radius: 50%;
    animation: ford-pulse 2s ease-in-out infinite;
    margin-right: 6px; vertical-align: middle;
}

/* ── Ford scan sweep animation ── */
@keyframes scan-sweep {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(400%); }
}
.ford-scan-line {
    position: absolute; top: 0; left: 0; width: 25%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(0,128,255,0.06), transparent);
    animation: scan-sweep 3s ease-in-out infinite;
    pointer-events: none;
}

/* ── Ford Card Components ── */
.terminal-card {
    background: linear-gradient(145deg, #08111e, #060e1a);
    border: 1px solid #0d1f35;
    border-radius: 10px;
    padding: 16px 18px;
    margin-bottom: 12px;
    position: relative;
    overflow: hidden;
    transition: border-color 0.22s, box-shadow 0.22s, transform 0.18s;
}
.terminal-card::before {
    content: '';
    position: absolute; inset: 0;
    background: linear-gradient(135deg, rgba(0,102,204,0.04) 0%, transparent 60%);
    pointer-events: none;
}
.terminal-card:hover {
    border-color: #0066cc;
    box-shadow: 0 4px 24px rgba(0,102,204,0.2), 0 0 0 1px rgba(0,102,204,0.12);
    transform: translateY(-2px);
}
.terminal-card .left-bar {
    position: absolute; top: 0; left: 0;
    width: 4px; height: 100%;
    border-radius: 10px 0 0 10px;
}
.card-symbol {
    font-size: 0.95rem; font-weight: 800; color: #f0f6ff;
    letter-spacing: 0.02em; text-shadow: 0 1px 8px rgba(0,128,255,0.15);
}
.card-strategy {
    font-size: 0.6rem; color: #5a7a9a; text-transform: uppercase;
    letter-spacing: 0.09em; margin-top: 2px; font-weight: 600;
}
.card-price {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.2rem; font-weight: 700;
}
.card-change {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem; font-weight: 600;
    text-align: right; margin-top: 2px;
}

/* ── Ford Pill Tags ── */
.pill {
    display: inline-block;
    background: #08111e; border: 1px solid #0d1f35;
    border-radius: 4px; padding: 2px 8px;
    font-size: 0.6rem; font-family: 'JetBrains Mono', monospace;
    font-weight: 600; color: #5a7a9a; margin: 2px 2px 0 0;
    white-space: nowrap; transition: border-color 0.15s;
}
.pill:hover { border-color: #0066cc; }
.pill-sl  { color: #ff4d4d !important; border-color: rgba(255,77,77,.25) !important;
    background: rgba(255,77,77,0.06) !important; }
.pill-tgt { color: #00c853 !important; border-color: rgba(0,200,83,.25) !important;
    background: rgba(0,200,83,0.06) !important; }
.pill-inst{ color: #a78bfa !important; border-color: rgba(167,139,250,.25) !important;
    background: rgba(167,139,250,0.06) !important; }
.pill-star{ color: #fb923c !important; border-color: rgba(251,146,60,.25) !important;
    background: rgba(251,146,60,0.06) !important; }
.pill-news{ color: #38bdf8 !important; border-color: rgba(56,189,248,.25) !important;
    background: rgba(56,189,248,0.06) !important; }
.pill-neg { color: #ff4d4d !important; border-color: rgba(255,77,77,.35) !important;
    background: rgba(255,77,77,0.1) !important; font-weight: 700 !important; }

/* ── Ford Section Headers ── */
.sec-hdr {
    display: flex; align-items: center; gap: 10px;
    padding: 14px 0 11px;
    border-bottom: 1px solid #0d1f35;
    margin-bottom: 16px;
    position: relative;
}
.sec-hdr::after {
    content: ''; position: absolute; bottom: -1px; left: 0;
    width: 48px; height: 2px;
    background: linear-gradient(90deg, #0066cc, transparent);
}
.sec-hdr-icon { font-size: 1.05rem; line-height: 1; }
.sec-hdr-title {
    font-size: 0.85rem; font-weight: 800; color: #f0f6ff;
    letter-spacing: 0.01em;
}
.sec-hdr-count {
    background: #08111e; border: 1px solid #0d1f35;
    border-radius: 20px; padding: 1px 10px;
    font-size: 0.66rem; font-weight: 700; color: #5a7a9a;
    font-family: 'JetBrains Mono', monospace;
}
.sec-hdr-badge {
    margin-left: auto;
    background: rgba(0,102,204,.12); color: #38bdf8;
    border: 1px solid rgba(0,102,204,.3);
    border-radius: 20px; padding: 2px 12px;
    font-size: 0.64rem; font-weight: 700; letter-spacing: 0.06em;
    text-transform: uppercase;
}

/* ── Ford Live Banner (chart tab) ── */
.live-banner {
    background: linear-gradient(145deg, #08111e, #060e1a);
    border: 1px solid #0d1f35;
    border-top: 2px solid #0066cc;
    border-radius: 10px; padding: 16px 22px;
    display: flex; gap: 30px; align-items: stretch;
    flex-wrap: wrap; margin-bottom: 18px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
.lb-item {
    display: flex; flex-direction: column;
    justify-content: center; min-width: 95px;
}
.lb-label {
    font-size: 0.6rem; color: #5a7a9a;
    text-transform: uppercase; letter-spacing: 0.09em;
    font-weight: 700; margin-bottom: 4px;
}
.lb-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.1rem; font-weight: 700; color: #f0f6ff;
}
.lb-sub { font-size: 0.64rem; color: #5a7a9a; margin-top: 2px; }
.lb-divider {
    width: 1px;
    background: linear-gradient(180deg, transparent, #0d1f35, transparent);
    align-self: stretch; margin: 0 6px;
}

/* ── Ford Ticker Strip ── */
.ticker-wrap {
    background: linear-gradient(145deg, #08111e, #060e1a);
    border: 1px solid #0d1f35;
    border-radius: 8px; padding: 0 16px;
    margin-bottom: 20px; overflow-x: auto;
    display: flex; gap: 0; align-items: stretch;
    scrollbar-width: none;
    box-shadow: 0 2px 16px rgba(0,0,0,0.25);
}
.ticker-wrap::-webkit-scrollbar { display: none; }
.ticker-cell {
    display: flex; flex-direction: column; justify-content: center;
    padding: 13px 22px 13px 0; min-width: 125px;
    border-right: 1px solid #0d1f35;
    transition: background 0.15s;
}
.ticker-cell:hover { background: rgba(0,102,204,0.06); }
.ticker-cell:first-child { padding-left: 4px; }
.ticker-cell:last-child { border-right: none; }
.ticker-name {
    font-size: 0.58rem; color: #5a7a9a;
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.09em;
}
.ticker-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.98rem; font-weight: 700; color: #f0f6ff; margin: 3px 0;
}
.ticker-chg {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.66rem; font-weight: 700;
}
.c-up { color: #00c853; }
.c-dn { color: #ff4d4d; }

/* ── Ford System Monitor Bar ── */
.ford-monitor {
    background: linear-gradient(135deg, #07101d, #08121f);
    border: 1px solid #0d1f35;
    border-left: 3px solid #0066cc;
    border-radius: 8px; padding: 10px 18px;
    margin-bottom: 16px;
    display: flex; justify-content: space-between;
    align-items: center; flex-wrap: wrap; gap: 10px;
}
.ford-monitor-label {
    font-size: 0.68rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.12em;
    color: #0066cc;
}
.ford-monitor-item {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem; color: #5a7a9a;
}
.ford-monitor-value { color: #38bdf8; font-weight: 700; }
.ford-monitor-good  { color: #00c853; font-weight: 700; }

/* ── Outcome markers ── */
.oc-hit { color: #00c853; font-weight: 700; }
.oc-sl  { color: #ff4d4d; font-weight: 700; }
.oc-act { color: #a78bfa; font-weight: 700; }

/* ── Ford Info/Alert Box ── */
.infobox {
    background: rgba(0,102,204,0.07);
    border: 1px solid rgba(0,102,204,0.2);
    border-left: 3px solid #0066cc;
    border-radius: 8px; padding: 12px 16px;
    font-size: 0.8rem; color: #8aaccc;
    margin-bottom: 14px; line-height: 1.7;
}

/* ── Ford News Sentiment Cards ── */
.news-neg-banner {
    background: rgba(255,77,77,0.08);
    border: 1px solid rgba(255,77,77,0.2);
    border-left: 3px solid #ff4d4d;
    border-radius: 6px; padding: 4px 10px;
    font-size: 0.65rem; font-weight: 700;
    color: #ff4d4d; display: inline-block;
    text-transform: uppercase; letter-spacing: 0.07em;
    margin-bottom: 4px;
}
.news-pos-banner {
    background: rgba(0,200,83,0.08);
    border: 1px solid rgba(0,200,83,0.2);
    border-left: 3px solid #00c853;
    border-radius: 6px; padding: 4px 10px;
    font-size: 0.65rem; font-weight: 700;
    color: #00c853; display: inline-block;
    text-transform: uppercase; letter-spacing: 0.07em;
    margin-bottom: 4px;
}

/* ── Ford Empty State ── */
.empty-state {
    text-align: center; padding: 80px 24px 90px;
}
.empty-state-icon {
    font-size: 3.5rem; margin-bottom: 18px;
    filter: drop-shadow(0 0 20px rgba(0,102,204,0.4));
}
.empty-state-title {
    font-size: 1.5rem; font-weight: 900; color: #f0f6ff;
    margin-bottom: 10px; letter-spacing: -0.01em;
}
.empty-state-sub {
    font-size: 0.84rem; color: #5a7a9a; max-width: 440px;
    margin: 0 auto 36px; line-height: 1.75;
}
.caps-grid { display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; }
.cap-card {
    background: linear-gradient(145deg, #08111e, #060e1a);
    border: 1px solid #0d1f35;
    border-radius: 10px; padding: 15px 20px;
    text-align: left; min-width: 145px;
    transition: border-color 0.2s, transform 0.18s;
}
.cap-card:hover { border-color: #0066cc; transform: translateY(-2px); }
.cap-lbl {
    font-size: 0.6rem; color: #5a7a9a;
    text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;
}
.cap-val {
    font-size: 0.84rem; color: #f0f6ff; font-weight: 700; margin-top: 5px;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Module imports
# ─────────────────────────────────────────────────────────────────────────────
import importlib
import tickers      as tick_helper
import data_provider as dp
import screeners    as scr
import institutional as inst
import news_provider as news_helper
import optimizer     as opt
import intraday_screener as intra
import analysis_history as hist

importlib.reload(tick_helper)
importlib.reload(dp)
importlib.reload(scr)
importlib.reload(inst)
importlib.reload(news_helper)
importlib.reload(opt)
importlib.reload(intra)
importlib.reload(hist)

# ─────────────────────────────────────────────────────────────────────────────
# Scheduled Analysis Trigger (for UptimeRobot / external cron)
# ─────────────────────────────────────────────────────────────────────────────
# Access: https://your-app.streamlit.app/?trigger_analysis=true
# Triggers Full Analysis on Nifty 1000 when pinged by UptimeRobot
try:
    if st.query_params.get("trigger_analysis") == "true":
        from scheduler import run_full_scheduled_analysis
        result = run_full_scheduled_analysis()
        st.markdown(f"**Scheduled Full Analysis Complete.** Generated picks on Nifty 1000.")
        st.stop()
except Exception:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# Session state init
# ─────────────────────────────────────────────────────────────────────────────
_SS_KEYS = ["screener_results", "past_signals_results", "news_picks",
            "news_past_results", "medium_term_picks", "data_cache",
            "screened_universe", "screened_strategy", "ltp_cache",
            "last_run_time", "last_sync_time", "last_sync_timestamp", "opt_leaderboard",
            "last_news_scrape_timestamp", "intraday_picks", "intraday_backtest",
            "is_analyzing", "analysis_universe", "analysis_index",
            "accumulated_matching", "accumulated_past_sigs", "accumulated_medium_term",
            "accumulated_intraday_picks", "accumulated_intraday_backtest",
            "accumulated_data_cache", "accumulated_ltp_cache", "bulk_deals_cached",
            "brokers_picks", "initial_news_loaded"]
for k in _SS_KEYS:
    if k not in st.session_state:
        if k in ["last_sync_timestamp", "last_news_scrape_timestamp"]:
            st.session_state[k] = 0.0
        elif k in ["is_analyzing"]:
            st.session_state[k] = False
        elif k == "news_picks":
            cache_file = "news_cache.json"
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        st.session_state[k] = pd.DataFrame(data) if data else pd.DataFrame()
                except Exception as e:
                    print(f"Error loading news cache: {e}")
                    st.session_state[k] = pd.DataFrame()
            else:
                st.session_state[k] = pd.DataFrame()
        elif k == "brokers_picks":
            cache_file = "brokers_cache.json"
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        st.session_state[k] = pd.DataFrame(data) if data else pd.DataFrame()
                except Exception as e:
                    print(f"Error loading brokers cache: {e}")
                    st.session_state[k] = pd.DataFrame()
            else:
                st.session_state[k] = pd.DataFrame()
        else:
            st.session_state[k] = None

if "_analysis_worker_state" not in st.session_state:
    st.session_state["_analysis_worker_state"] = {}

# ─── Startup: load a fast news preview first, then refresh in the background ───
if st.session_state.get("initial_news_loaded") is not True:
    st.session_state.initial_news_loaded = True
    st.session_state.news_picks = pd.DataFrame()

    try:
        if os.path.exists("news_cache.json"):
            with open("news_cache.json", "r", encoding="utf-8") as _f:
                cached_items = json.load(_f)
            today_str = datetime.date.today().isoformat()
            today_items = [x for x in cached_items if x.get("Date", "") >= today_str]
            if today_items:
                st.session_state.news_picks = pd.DataFrame(today_items)

        if st.session_state.news_picks.empty:
            preview_items = news_helper.get_news_preview(
                all_symbols=tick_helper.get_all_nse_tickers(),
                existing_picks=[]
            )
            st.session_state.news_picks = pd.DataFrame(preview_items)

        # ADD: Load latest full analysis run globally
        try:
            history_cache_path = "analysis_history_cache.json"
            if os.path.exists(history_cache_path):
                with open(history_cache_path, "r", encoding="utf-8") as _hf:
                    hist_data = json.load(_hf)
                if hist_data.get("runs") and len(hist_data["runs"]) > 0:
                    latest_run = hist_data["runs"][0]
                    picks = latest_run.get("picks", [])
                    if picks:
                        all_picks_df = pd.DataFrame(picks)
                        
                        swing = all_picks_df[all_picks_df["Source"] == "swing"]
                        st.session_state.screener_results = swing if not swing.empty else pd.DataFrame()
                        
                        med = all_picks_df[all_picks_df["Source"] == "medium"]
                        st.session_state.medium_term_picks = med if not med.empty else pd.DataFrame()
                        
                        intra_p = all_picks_df[all_picks_df["Source"] == "intraday"]
                        st.session_state.intraday_picks = intra_p if not intra_p.empty else pd.DataFrame()

                        st.session_state.screened_universe = latest_run.get("universe", "Nifty 1000")
                        st.session_state.screened_strategy = latest_run.get("strategy", "All Strategies")
                        st.session_state.last_run_time = "Global Cache (Loaded)"
                        st.session_state.last_sync_time = "Global Cache (Loaded)"
                        st.session_state.last_sync_timestamp = time.time()
        except Exception as e:
            print(f"Error loading global cache: {e}")

    except Exception as startup_err:
        print(f"[Startup News] Error: {startup_err}")
        st.session_state.news_picks = pd.DataFrame()

    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:20px 0 4px;text-align:center;">
      <div style="font-size:0.5rem;letter-spacing:0.35em;color:#0066cc;font-weight:900;text-transform:uppercase;margin-bottom:6px;">▬▬▬ FORD ▬▬▬</div>
      <div style="font-size:1.6rem;font-weight:900;color:#f0f6ff;letter-spacing:-0.02em;line-height:1;">NSE PULSE</div>
      <div style="font-size:0.6rem;color:#5a7a9a;text-transform:uppercase;letter-spacing:.16em;margin-top:5px;font-weight:700;">Trading Intelligence</div>
      <div style="margin:10px auto 0;width:40px;height:2px;background:linear-gradient(90deg,transparent,#0066cc,transparent);"></div>
    </div>
    <div style="margin:14px 0;padding:8px 12px;background:rgba(0,102,204,0.08);border:1px solid rgba(0,102,204,0.18);
                border-radius:6px;display:flex;align-items:center;gap:8px;">
      <span style="width:7px;height:7px;border-radius:50%;background:#00c853;
                   display:inline-block;animation:ford-pulse 2s infinite;"></span>
      <span style="font-size:0.68rem;color:#5a7a9a;font-weight:700;">NSE MARKET</span>
      <span style="font-size:0.68rem;color:#00c853;font-weight:800;margin-left:auto;">LIVE</span>
    </div>
    <div style="height:1px;background:linear-gradient(90deg,transparent,#0d1f35,transparent);margin:2px 0 14px;"></div>
    """, unsafe_allow_html=True)

    stock_universe = st.selectbox(
        "Stock Universe",
        ["Nifty 50", "Nifty 100", "F&O Stocks (Intraday)", "Nifty 500", "Nifty 1000", "Custom"],
        index=4,
    )
    custom_tickers = ""
    if stock_universe == "Custom":
        custom_tickers = st.text_area("Symbols (comma-separated)",
                                      "RELIANCE, TCS, HDFCBANK, SBIN, INFY",
                                      height=80)

    selected_strategy = st.selectbox(
        "Swing Strategy",
        ["All Strategies", "EMA Pullback (20)", "RSI Reversal & Pullback",
         "Volume Breakout", "MACD Crossover", "Bollinger Rebound"],
    )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    min_price     = st.number_input("Min Price (₹)", min_value=1.0, value=20.0, step=10.0)
    min_vol_ratio = st.slider("Min Volume Ratio", 0.5, 5.0, 1.0, 0.1)
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    auto_refresh = st.checkbox("🔄 Auto-Refresh (1m)", value=True, help="Auto-sync live prices and news feeds every 60 seconds.")
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    load_news_btn = st.button("📰 Load Full News Coverage", key="load_news_btn")
    run_full_btn = st.button("🔥 Run Full Analysis (Nifty 1000)", key="run_full_btn")

    st.markdown("""
    <hr style="border:none;border-top:1px solid #21262d;margin:14px 0 10px;">
    <div style="font-size:0.65rem;color:#4a5568;text-align:center;line-height:1.9;">
      Data: NSE India · yfinance<br>
      Live Prices: NSE JSON · nselib<br>
      News: ET · Moneycontrol · Livemint · NSE · Google News RSS<br>
      Strategies: 5 Short + 2 Medium-term
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Ford Header
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding:8px 0 16px;
            border-bottom:2px solid #0d1f35;
            margin-bottom:20px;
            display:flex;align-items:center;justify-content:space-between;
            flex-wrap:wrap;gap:10px;">
  <div style="display:flex;align-items:center;gap:14px;">
    <div style="width:4px;height:42px;background:linear-gradient(180deg,#0080ff,#0040aa);
                border-radius:4px;flex-shrink:0;"></div>
    <div>
      <div style="font-size:1.45rem;font-weight:900;color:#f0f6ff;
                  letter-spacing:-0.02em;line-height:1.15;">
        NSE <span style="color:#0080ff;">PULSE</span>
        <span style="font-size:0.65rem;font-weight:700;color:#5a7a9a;
                     letter-spacing:0.12em;text-transform:uppercase;
                     vertical-align:middle;margin-left:10px;
                     background:#08111e;border:1px solid #0d1f35;
                     padding:2px 8px;border-radius:4px;">PRO</span>
      </div>
      <div style="font-size:0.7rem;color:#5a7a9a;margin-top:3px;font-weight:600;
                  letter-spacing:0.04em;">
        Real-time NSE · Swing Intelligence · Institutional Flow · News Catalyst Engine
      </div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:16px;">
    <div style="text-align:right;">
      <div style="font-size:0.62rem;color:#5a7a9a;font-weight:700;
                  text-transform:uppercase;letter-spacing:0.1em;">Market Time</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.92rem;
                  color:#f0f6ff;font-weight:700;">{ts}</div>
    </div>
    <div style="width:1px;height:32px;background:#0d1f35;"></div>
    <div style="display:flex;align-items:center;gap:6px;
                background:rgba(0,200,83,0.1);
                border:1px solid rgba(0,200,83,0.2);
                border-radius:20px;padding:4px 12px;">
      <span class="live-dot"></span>
      <span style="color:#00c853;font-weight:800;font-size:0.7rem;
                   letter-spacing:0.1em;">LIVE</span>
    </div>
  </div>
</div>
""".format(ts=datetime.datetime.now().strftime("%d %b  %H:%M:%S")), unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Live Index Ticker Strip
# ─────────────────────────────────────────────────────────────────────────────
live_indices = dp.get_live_nse_indices()
idx_map = {d["name"]: d for d in live_indices}
WANTED = ["NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY MIDCAP 100", "NIFTY 500"]

cells_html = ""
for name in WANTED:
    short = name.replace("NIFTY ", "")
    if name in idx_map:
        d   = idx_map[name]
        cls = "c-up" if d["pChange"] >= 0 else "c-dn"
        sym = "▲" if d["pChange"] >= 0 else "▼"
        cells_html += f"""
        <div class="ticker-cell">
          <div class="ticker-name">{short}</div>
          <div class="ticker-val">{d['last']:,.2f}</div>
          <div class="ticker-chg {cls}">{sym} {abs(d['pChange']):.2f}%  {d['change']:+.2f}</div>
        </div>"""
    else:
        cells_html += f"""
        <div class="ticker-cell">
          <div class="ticker-name">{short}</div>
          <div class="ticker-val" style="color:#4a5568;">—</div>
          <div class="ticker-chg" style="color:#4a5568;">NSE API</div>
        </div>"""

# FII
fii_flow, fii_date = inst.get_latest_fii_sentiment()
if fii_flow is not None:
    fc  = "c-up" if fii_flow >= 0 else "c-dn"
    fs  = "▲" if fii_flow >= 0 else "▼"
    cells_html += f"""
    <div class="ticker-cell" style="min-width:150px;">
      <div class="ticker-name">FII Flow · {fii_date}</div>
      <div class="ticker-val {fc}" style="font-size:.88rem;">₹{fii_flow:+,.0f} Cr</div>
      <div class="ticker-chg {fc}">{fs} Net Equity Buy/Sell</div>
    </div>"""

# Live timestamp cell
cells_html += f"""
<div class="ticker-cell" style="min-width:90px;margin-left:auto;align-items:flex-end;border-right:none;">
  <div class="ticker-name">Updated</div>
  <div class="ticker-val" style="font-size:.78rem;color:#6e7f96;">{datetime.datetime.now().strftime('%H:%M:%S')}</div>
  <div style="font-size:.6rem;color:#3fb950;font-weight:700;display:flex;align-items:center;gap:3px;margin-top:2px;">
    <span class="live-dot"></span>LIVE
  </div>
</div>"""

st.markdown(f'<div class="ticker-wrap">{cells_html}</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Batch LTP fetch helper  (called ONCE per analysis run, cached in session)
# ─────────────────────────────────────────────────────────────────────────────
def _get_ltp_cache(tickers: list, data_cache: dict) -> dict:
    """
    Fetches live LTP for each ticker via nsepython/yfinance in a highly optimized way.
    Attempts instant nsepython quotes first. If any fail, it runs a SINGLE batch yfinance
    intraday download rather than sequential downloads, preventing UI lag.
    """
    if not tickers:
        return {}
    
    ltp_map = {}
    failed_tickers = []
    
    # 1. Try nsepython (instant during market hours)
    for ticker in tickers:
        sym = ticker.replace(".NS", "")
        try:
            from nsepython import nse_quote_ltp
            ltp = nse_quote_ltp(sym, series="EQ")
            if ltp and float(ltp) > 0:
                ltp_map[ticker] = float(ltp)
                continue
        except Exception:
            pass
        failed_tickers.append(ticker)
        
    # 2. Try single batch yfinance download for failed tickers (takes <1s for all tickers combined)
    if failed_tickers:
        try:
            import yfinance as yf
            data = yf.download(tickers=failed_tickers, period="1d", interval="1m", auto_adjust=True, progress=False)
            if not data.empty:
                if isinstance(data.columns, pd.MultiIndex):
                    for t in failed_tickers:
                        try:
                            df = data.xs(t, axis=1, level=1)
                            close_col = df['Close'].dropna()
                            if not close_col.empty:
                                ltp_map[t] = float(close_col.iloc[-1])
                        except Exception:
                            pass
                else:
                    # Single ticker case
                    close_col = data['Close'].dropna()
                    if not close_col.empty:
                        ltp_map[failed_tickers[0]] = float(close_col.iloc[-1])
        except Exception:
            pass
            
    # 3. Fallback to cached daily Close price
    for ticker in tickers:
        if ticker not in ltp_map or ltp_map[ticker] <= 0:
            if data_cache and ticker in data_cache:
                ltp_map[ticker] = float(data_cache[ticker]['Close'].iloc[-1])
            else:
                ltp_map[ticker] = 0.0
                
    return ltp_map

# ─────────────────────────────────────────────────────────────────────────────
# UI helpers
# ─────────────────────────────────────────────────────────────────────────────
_STRATEGY_COLORS = {
    "EMA Pullback (20)":       "#58a6ff",
    "RSI Reversal (Oversold)": "#3fb950",
    "RSI Pullback (Uptrend)":  "#56d364",
    "Volume Breakout":         "#d2a8ff",
    "MACD Crossover":          "#79c0ff",
    "Bollinger Rebound":       "#ffa657",
    "EMA Crossover (20/50)":   "#58a6ff",
    "BB Squeeze Breakout":     "#d2a8ff",
    "Supertrend Reversal":     "#ff55aa",
    "ADX Trend Strength":      "#38bdf8",
    "VWAP Bounce (Long)":      "#58a6ff",
    "ORB Breakout (Long)":     "#56d364",
    "EMA 9/21 Crossover (Long)":"#d2a8ff",
    "VWAP Rejection (Short)":  "#ff4d4d",
    "Gap-Down Continuation (Short)": "#ff4d4d",
    "EMA 9/21 Crossover (Short)":"#ff55aa",
}

def _sec_header(icon: str, title: str, count=None, badge: str = ""):
    cnt_html = f'<span class="sec-hdr-count">{count}</span>' if count is not None else ""
    bdg_html = f'<span class="sec-hdr-badge">{badge}</span>' if badge else ""
    st.markdown(
        f'<div class="sec-hdr"><span class="sec-hdr-icon">{icon}</span>'
        f'<span class="sec-hdr-title">{title}</span>{cnt_html}{bdg_html}</div>',
        unsafe_allow_html=True,
    )

def _ensure_ticker_column(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize pick/news DataFrames so a Ticker column always exists."""
    if df is None:
        return pd.DataFrame()
    if isinstance(df, pd.Series):
        df = df.to_frame().T
    out = df.copy()
    if "Ticker" not in out.columns and "Symbol" in out.columns:
        out["Ticker"] = out["Symbol"].fillna("")
    elif "Ticker" not in out.columns:
        out["Ticker"] = ""
        
    # Safeguard missing UI columns (especially for old cached data)
    if not out.empty:
        if "High_Conviction" not in out.columns:
            out["High_Conviction"] = False
        if "Strategy" not in out.columns:
            out["Strategy"] = ""
        if "Type" not in out.columns:
            out["Type"] = "BUY"
            
    return out


def _safe_df(records):
    if not records:
        return pd.DataFrame()
    df_out = pd.DataFrame(records)
    for col in df_out.columns:
        if pd.api.types.is_object_dtype(df_out[col]) or pd.api.types.is_string_dtype(df_out[col]):
            converted = pd.to_numeric(df_out[col], errors='coerce')
            non_missing = df_out[col].notna()
            if non_missing.any() and converted.notna().sum() == non_missing.sum():
                df_out[col] = converted
    return df_out


_ANALYSIS_STATE_LOCK = threading.Lock()


def _reset_analysis_worker_state():
    with _ANALYSIS_STATE_LOCK:
        st.session_state["_analysis_worker_state"] = {}


def _clear_analysis_session_state():
    _reset_analysis_worker_state()
    st.session_state.is_analyzing = False
    st.session_state.analysis_universe = []
    st.session_state.analysis_index = 0
    st.session_state.analysis_batch = 0
    st.session_state.analysis_total_batches = 0
    st.session_state.analysis_status = "Ready"
    st.session_state.analysis_mode = None
    st.session_state.screened_universe = None
    st.session_state.screened_strategy = None
    st.session_state.accumulated_matching = []
    st.session_state.accumulated_past_sigs = []
    st.session_state.accumulated_medium_term = []
    st.session_state.accumulated_intraday_picks = []
    st.session_state.accumulated_intraday_backtest = []
    st.session_state.accumulated_data_cache = {}
    st.session_state.accumulated_ltp_cache = {}
    st.session_state.data_cache = {}
    st.session_state.ltp_cache = {}
    st.session_state.bulk_deals_cached = None
    st.session_state.screener_results = pd.DataFrame()
    st.session_state.past_signals_results = pd.DataFrame()
    st.session_state.medium_term_picks = pd.DataFrame()
    st.session_state.intraday_picks = pd.DataFrame()
    st.session_state.intraday_backtest = pd.DataFrame()
    st.session_state.news_picks = pd.DataFrame()
    st.session_state.news_past_results = pd.DataFrame()
    st.session_state.last_run_time = "Ready"
    st.session_state.last_sync_time = "Ready"
    st.session_state.last_sync_timestamp = 0.0
    st.session_state.last_news_scrape_timestamp = 0.0


def _get_analysis_worker_state():
    with _ANALYSIS_STATE_LOCK:
        return st.session_state.get("_analysis_worker_state")


def _sync_worker_state_to_session(worker_state):
    if not worker_state:
        return

    progress = worker_state.get("progress", {}) or {}
    st.session_state.analysis_index = int(progress.get("processed", st.session_state.analysis_index or 0))
    st.session_state.analysis_status = progress.get("status", "Preparing batch...")
    st.session_state.analysis_batch = int(progress.get("batch", 0) or 0)
    st.session_state.analysis_total_batches = int(progress.get("total_batches", 0) or 0)
    st.session_state.accumulated_matching = list(worker_state.get("accumulated_matching", []))
    st.session_state.accumulated_past_sigs = list(worker_state.get("accumulated_past_sigs", []))
    st.session_state.accumulated_medium_term = list(worker_state.get("accumulated_medium_term", []))
    st.session_state.accumulated_intraday_picks = list(worker_state.get("accumulated_intraday_picks", []))
    st.session_state.accumulated_intraday_backtest = list(worker_state.get("accumulated_intraday_backtest", []))
    st.session_state.accumulated_data_cache = dict(worker_state.get("data_cache", {}))
    st.session_state.accumulated_ltp_cache = dict(worker_state.get("ltp_cache", {}))
    st.session_state.bulk_deals_cached = worker_state.get("bulk_deals_cached")

    st.session_state.screener_results = _safe_df(st.session_state.accumulated_matching)
    st.session_state.past_signals_results = _safe_df(st.session_state.accumulated_past_sigs)
    st.session_state.medium_term_picks = _safe_df(st.session_state.accumulated_medium_term)
    st.session_state.intraday_picks = _safe_df(st.session_state.accumulated_intraday_picks)
    st.session_state.intraday_backtest = _safe_df(st.session_state.accumulated_intraday_backtest)
    st.session_state.data_cache = st.session_state.accumulated_data_cache
    st.session_state.ltp_cache = st.session_state.accumulated_ltp_cache

    news_picks = worker_state.get("news_picks")
    if news_picks is not None:
        st.session_state.news_picks = pd.DataFrame(news_picks) if news_picks else pd.DataFrame()
    news_bt = worker_state.get("news_past_results")
    if news_bt is not None:
        st.session_state.news_past_results = pd.DataFrame(news_bt) if news_bt else pd.DataFrame()

    st.session_state.last_sync_timestamp = time.time()


# ─────────────────────────────────────────────────────────────────────────────
# Universe resolver helper
# ─────────────────────────────────────────────────────────────────────────────
def _resolve_universe_tickers(stock_universe: str, custom_tickers: str) -> list:
    """Resolve the selected universe to a list of tickers."""
    if stock_universe == "Nifty 50":
        return tick_helper.get_nifty50_tickers()
    elif stock_universe == "Nifty 100":
        return tick_helper.get_nifty100_tickers()
    elif stock_universe == "F&O Stocks (Intraday)":
        return tick_helper.get_fno_tickers()
    elif stock_universe == "Nifty 500":
        with st.status("Fetching Nifty 500 constituents...", expanded=False) as s:
            raw = tick_helper.get_nifty500_tickers()
            s.update(label=f"Nifty 500: {len(raw)} stocks", state="complete")
            return raw
    elif stock_universe == "Nifty 1000":
        with st.status("Building Nifty 1000 list...", expanded=False) as s:
            raw = tick_helper.get_nifty1000_tickers()
            s.update(label=f"Nifty 1000: {len(raw)} stocks", state="complete")
            return raw
    else:
        syms = [s.strip().upper() for s in custom_tickers.split(",") if s.strip()]
        return [f"{s}.NS" if not s.endswith(".NS") else s for s in syms]


# ─────────────────────────────────────────────────────────────────────────────
# Background worker
# ─────────────────────────────────────────────────────────────────────────────
def _run_background_analysis_worker(raw, strategy, min_price, min_vol_ratio, state):
    try:
        total = len(raw)
        total_batches = int(np.ceil(total / 10)) if total else 0
        state["active"] = True
        state["done"] = False
        state["error"] = None
        state["progress"] = {"processed": 0, "total": total, "batch": 0, "total_batches": total_batches, "status": "Preparing first batch..."}
        state["accumulated_matching"] = []
        state["accumulated_past_sigs"] = []
        state["accumulated_medium_term"] = []
        state["accumulated_intraday_picks"] = []
        state["accumulated_intraday_backtest"] = []
        state["data_cache"] = {}
        state["ltp_cache"] = {}
        state["bulk_deals_cached"] = None
        state["news_picks"] = []
        state["news_past_results"] = []
        state["last_updated"] = time.time()

        bulk_deals = []

        for idx in range(0, total, 10):
            chunk = raw[idx:idx + 10]
            batch_num = idx // 10 + 1
            state["progress"] = {
                "processed": min(idx + 1, total),
                "total": total,
                "batch": batch_num,
                "total_batches": total_batches,
                "status": f"Scanning batch {batch_num}/{total_batches}"
            }
            state["last_updated"] = time.time()

            chunk_data = dp.download_stock_data_batch(chunk, period="1y")
            state["data_cache"].update(chunk_data)

            if idx == 0 or state["bulk_deals_cached"] is None:
                try:
                    state["bulk_deals_cached"] = inst.get_recent_bulk_deals()
                except Exception as bd_err:
                    print(f"Bulk deals fetch failed: {bd_err}")
                    state["bulk_deals_cached"] = []
            bulk_deals = state["bulk_deals_cached"]

            matching, past_sigs, medium_term = [], [], []
            intraday_picks, intraday_backtest = [], []
            for ticker, df in chunk_data.items():
                try:
                    if float(df['Close'].iloc[-1]) < min_price:
                        continue
                    res = scr.run_screener_on_data(ticker, df, strategy)
                    if res and float(res.get('Vol_Ratio', 0)) >= min_vol_ratio:
                        matching.append(res)
                    past_sigs.extend(scr.track_past_signals(ticker, df, strategy))
                    mt = scr.run_medium_term_screener(ticker, df)
                    if mt:
                        medium_term.append(mt)
                    intra_res = intra.run_intraday_screener(ticker, df)
                    if intra_res:
                        intraday_picks.extend(intra_res)
                    intraday_backtest.extend(intra.backtest_intraday_10days(ticker, df))
                    
                    # Harmony Pattern Detection
                    try:
                        harmony_res = scr.detect_harmony_patterns(df)
                        if harmony_res:
                            harmony_res["Ticker"] = ticker
                            matching.append(harmony_res)
                    except Exception:
                        pass
                except Exception:
                    continue

            try:
                matching = inst.enrich_picks_with_bulk_deals(matching, bulk_deals)
                medium_term = inst.enrich_picks_with_bulk_deals(medium_term, bulk_deals)
            except Exception as enrich_err:
                print(f"[Batch {batch_num}] Enrichment failed: {enrich_err}")

            state["accumulated_matching"].extend(matching)
            state["accumulated_past_sigs"].extend(past_sigs)
            state["accumulated_medium_term"].extend(medium_term)
            state["accumulated_intraday_picks"].extend(intraday_picks)
            state["accumulated_intraday_backtest"].extend(intraday_backtest)

            try:
                new_pick_tickers = list({
                    r.get("Ticker", "") for r in matching + medium_term + intraday_picks
                    if r.get("Ticker", "")
                })
                if new_pick_tickers:
                    batch_ltps = _get_ltp_cache(new_pick_tickers, chunk_data)
                    state["ltp_cache"].update(batch_ltps)
            except Exception as ltp_err:
                print(f"[Batch {batch_num}] LTP fetch failed: {ltp_err}")

            state["progress"] = {
                "processed": min(idx + len(chunk), total),
                "total": total,
                "batch": batch_num,
                "total_batches": total_batches,
                "status": f"Batch {batch_num}/{total_batches} completed"
            }
            state["last_updated"] = time.time()

        all_nse_symbols = tick_helper.get_all_nse_tickers()
        import json
        import os
        existing_news_list = []
        if os.path.exists("news_cache.json"):
            try:
                with open("news_cache.json", "r", encoding="utf-8") as f:
                    existing_news_list = json.load(f)
            except Exception:
                pass
        news_picks = news_helper.get_today_news_recommendations(state["data_cache"], all_symbols=all_nse_symbols, existing_picks=existing_news_list)
        # Pass previously computed news picks (from cache) to the backtest so it can backtest
        # BOTH hardcoded historical events AND actual previously-computed trade recommendations
        cached_computed_picks = [p for p in existing_news_list if p.get("Price") and p.get("Stop Loss") and p.get("Target")]
        news_bt = news_helper.run_news_backtest(state["data_cache"], lookback_days=30, cached_news_items=cached_computed_picks)
        state["news_picks"] = news_picks or []
        state["news_past_results"] = news_bt or []

        # Fetch broker picks and persist 30-day cache
        try:
            try:
                broker_calls = news_helper.fetch_broker_calls(all_symbols=all_nse_symbols, max_items=60)
            except Exception:
                broker_calls = []
            state["brokers_picks"] = broker_calls or []
            # Persist merged broker cache and prune to 30 days
            try:
                existing_map = {}
                if os.path.exists("brokers_cache.json"):
                    try:
                        with open("brokers_cache.json", "r", encoding="utf-8") as _f:
                            for _item in json.load(_f):
                                existing_map[_item.get("Headline", "")] = _item
                    except Exception:
                        existing_map = {}
                for _p in state["brokers_picks"]:
                    existing_map[_p.get("Headline", "")] = _p
                merged_all = list(existing_map.values())
                # prune via provider utility if available
                try:
                    merged_all = news_helper.prune_cache_by_days(merged_all, days=30, date_key='Date')
                except Exception:
                    pass
                with open("brokers_cache.json", "w", encoding="utf-8") as _f:
                    json.dump(merged_all, _f, indent=2, ensure_ascii=False)
            except Exception as _bcerr:
                print(f"Error persisting brokers cache: {_bcerr}")
        except Exception:
            pass

        # Persist merged news cache so future runs reuse previous results (preserve entire history)
        try:
            existing_map = {}
            if os.path.exists("news_cache.json"):
                try:
                    with open("news_cache.json", "r", encoding="utf-8") as _f:
                        for _item in json.load(_f):
                            existing_map[_item.get("Headline", "")] = _item
                except Exception:
                    existing_map = {}
            for _p in state["news_picks"]:
                existing_map[_p.get("Headline", "")] = _p
            merged_all = list(existing_map.values())
            with open("news_cache.json", "w", encoding="utf-8") as _f:
                json.dump(merged_all, _f, indent=2, ensure_ascii=False)
        except Exception as _cache_err:
            print(f"Error persisting news cache after background analysis: {_cache_err}")

        # Save analysis history for persistence and validation
        try:
            import analysis_history as hist
            history_cache = hist.load_history_cache()
            
            # Collect all picks from this run
            all_picks = []
            for pick in state.get("accumulated_matching", []):
                p = dict(pick)
                p["Source"] = "swing"
                all_picks.append(p)
            for pick in state.get("accumulated_medium_term", []):
                p = dict(pick)
                p["Source"] = "medium"
                all_picks.append(p)
            for pick in state.get("accumulated_intraday_picks", []):
                p = dict(pick)
                p["Source"] = "intraday"
                all_picks.append(p)
            for pick in state.get("news_picks", []):
                p = dict(pick)
                p["Source"] = "news"
                all_picks.append(p)
            
            # Validate previous picks and add this run to history
            hist.add_run_to_history(
                history_cache,
                date_str=datetime.date.today().isoformat(),
                universe=state.get("universe", ""),
                strategy=state.get("strategy", ""),
                mode="full",
                pick_list=all_picks,
            )
            
            # Validate broker calls against current prices
            current_price_map = {}
            for pick in all_picks:
                ticker = pick.get("Ticker") or pick.get("Symbol") or ""
                price = pick.get("Price")
                if ticker and price:
                    current_price_map[ticker] = float(price)
            hist.validate_broker_calls(history_cache, current_price_map)
        except Exception as he:
            print(f"Error saving analysis history: {he}")

        state["done"] = True
        state["active"] = False
        state["progress"] = {"processed": total, "total": total, "batch": total_batches, "total_batches": total_batches, "status": "Finalizing results..."}
        state["last_updated"] = time.time()
    except Exception as exc:
        state["done"] = True
        state["active"] = False
        state["error"] = str(exc)
        state["last_updated"] = time.time()


def _start_background_analysis(raw, strategy, min_price, min_vol_ratio, mode="full"):
    _reset_analysis_worker_state()
    state = {
        "active": True,
        "done": False,
        "error": None,
        "mode": mode,
        "progress": {"processed": 0, "total": len(raw), "batch": 0, "total_batches": int(np.ceil(len(raw) / 10)) if raw else 0},
        "accumulated_matching": [],
        "accumulated_past_sigs": [],
        "accumulated_medium_term": [],
        "accumulated_intraday_picks": [],
        "accumulated_intraday_backtest": [],
        "data_cache": {},
        "ltp_cache": {},
        "bulk_deals_cached": None,
        "news_picks": [],
        "news_past_results": [],
        "last_updated": time.time(),
    }
    with _ANALYSIS_STATE_LOCK:
        st.session_state["_analysis_worker_state"] = state
    thread = threading.Thread(
        target=_run_background_analysis_worker,
        args=(raw, strategy, min_price, min_vol_ratio, state),
        daemon=True,
    )
    thread.start()
    return state, thread


def _render_cards(df: pd.DataFrame, ltp_map: dict, card_type: str = "short"):
    """
    Renders stock pick cards in a 3-column grid.
    ltp_map: pre-fetched dict {ticker -> ltp_float}
    """
    df = _ensure_ticker_column(df)
    if df is None or df.empty:
        st.markdown('<div class="infobox">No picks for this section today.</div>',
                    unsafe_allow_html=True)
        return

    rows = df.to_dict("records")
    # Render in rows of 3
    for row_start in range(0, len(rows), 3):
        chunk = rows[row_start:row_start + 3]
        cols  = st.columns(len(chunk))
        for col, row in zip(cols, chunk):
            ticker  = row.get("Ticker", "")
            symbol  = ticker.replace(".NS", "") if isinstance(ticker, str) and ticker else ""
            if not symbol:
                symbol = row.get("Symbol", "") or "MARKET"
            strat   = row.get("Strategy", "—")
            sl      = row.get("Stop Loss", "")
            tgt     = row.get("Target", "")
            rr      = row.get("Risk_Reward", "")
            rsi_v   = row.get("RSI", None)
            vol_r   = row.get("Vol_Ratio", None)
            prev    = float(row.get("Price", 0) or 0)
            show_price = bool(ticker) and prev > 0
            ltp     = ltp_map.get(ticker, prev) or prev if show_price else prev
            bar_col = _STRATEGY_COLORS.get(strat, "#1f6feb")

            chg_pct   = ((ltp - prev) / prev * 100) if prev else 0.0
            ltp_color = "#3fb950" if chg_pct >= 0 else "#f85149"
            arrow     = "▲" if chg_pct >= 0 else "▼"

            # Pill HTML
            pills = ""
            if sl:  pills += f'<span class="pill pill-sl">SL ₹{sl}</span>'
            if tgt: pills += f'<span class="pill pill-tgt">TGT ₹{tgt}</span>'
            if rr:  pills += f'<span class="pill">{rr}</span>'
            if rsi_v is not None:
                pills += f'<span class="pill">RSI {rsi_v:.1f}</span>'
            if vol_r and float(vol_r) > 0:
                pills += f'<span class="pill">{float(vol_r):.1f}x Vol</span>'

            extra = ""
            if row.get("Type") == "SELL-BUY":
                extra = '<span class="pill pill-neg">🔴 SHORT</span>'
            elif row.get("Superstar_Buying"):
                names = row.get("Superstar_Names", "Superstar")
                extra = f'<span class="pill pill-star">🔥 {names}</span>'
            elif row.get("High_Conviction"):
                extra = '<span class="pill pill-inst">💎 Institutional</span>'
            elif card_type == "news":
                cat = row.get("Catalyst", "News")
                scope = row.get("Scope", "Stock")
                scope_badge = "🌍 Market-wide" if scope == "Market" else "📰 Stock catalyst"
                extra = f'<span class="pill pill-news">{scope_badge}</span><span class="pill pill-news">📰 {cat}</span>'

            with col:
                st.markdown(f"""
                <div class="terminal-card">
                  <div class="left-bar" style="background:{bar_col};"></div>
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
                    <div>
                      <div class="card-symbol">{symbol}</div>
                      <div class="card-strategy">{strat}</div>
                    </div>
                    <div style="text-align:right;">
                      <div class="card-price" style="color:{ltp_color};">{f'₹{ltp:,.2f}' if show_price else 'Market-wide'}</div>
                      <div class="card-change" style="color:{ltp_color};">{f'{arrow} {abs(chg_pct):.2f}%' if show_price else 'Macro / sector impact'}</div>
                    </div>
                  </div>
                  <div>{pills}{extra}</div>
                </div>""", unsafe_allow_html=True)


def _highlight_status(row):
    s, p = row.get("Status", ""), row.get("P&L (%)", 0)
    if s == "Target Hit":
        return f"🟢 +{p:.2f}%"
    elif s == "Stop Loss Hit":
        return f"🔴 {p:.2f}%"
    else:
        return f"🟡 {p:+.2f}%"


def _bt_table(df_bt, extra_cols=None):
    if df_bt is None or df_bt.empty:
        st.markdown('<div class="infobox">No trades for this period.</div>',
                    unsafe_allow_html=True)
        return
    d = df_bt.sort_values("Trigger Date", ascending=False).copy()
    d["Outcome"] = d.apply(_highlight_status, axis=1)
    # Coerce numeric columns to prevent PyArrow serialization ArrowTypeError on mixed types
    for numeric_col in ["Entry Price", "Target", "Stop Loss", "Current/Exit", "Days Held"]:
        if numeric_col in d.columns:
            d[numeric_col] = pd.to_numeric(d[numeric_col], errors='coerce')
    base = ["Trigger Date", "Ticker", "Strategy", "Entry Price",
            "Target", "Stop Loss", "Current/Exit", "Days Held", "Outcome"]
    cols = [c for c in base + (extra_cols or []) if c in d.columns]
    st.dataframe(
        d[cols],
        column_config={
            "Entry Price":  st.column_config.NumberColumn("Entry (₹)",  format="₹%.2f"),
            "Target":       st.column_config.NumberColumn("Target (₹)", format="₹%.2f"),
            "Stop Loss":    st.column_config.NumberColumn("SL (₹)",     format="₹%.2f"),
            "Current/Exit": st.column_config.NumberColumn("Exit (₹)",   format="₹%.2f"),
            "Days Held":    st.column_config.NumberColumn("Days"),
            "High_Conviction":      st.column_config.CheckboxColumn("Inst."),
            "Institutional_Details":st.column_config.TextColumn("Institutional Details"),
            "Headline":     st.column_config.TextColumn("News Headline"),
            "Catalyst":     st.column_config.TextColumn("Catalyst"),
        },
        hide_index=True, width='stretch',
    )


def _bt_stats(df_bt):
    if df_bt is None or df_bt.empty:
        return
    hits   = len(df_bt[df_bt["Status"] == "Target Hit"])
    losses = len(df_bt[df_bt["Status"] == "Stop Loss Hit"])
    wr     = hits / (hits + losses) * 100 if (hits + losses) > 0 else 0.0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Trades",  len(df_bt))
    c2.metric("🟢 Target Hit", hits)
    c3.metric("🔴 Stop Loss",  losses)
    c4.metric("Win Rate", f"{wr:.1f}%" if (hits + losses) > 0 else "N/A")


# ─────────────────────────────────────────────────────────────────────────────
# Run Analysis Logic
# ─────────────────────────────────────────────────────────────────────────────
if load_news_btn:
    st.session_state.is_analyzing = False
    try:
        with st.status("🔄 Loading full news coverage from multiple sources...", expanded=True) as status:
            status.write("📡 Fetching from Economic Times, Moneycontrol, Livemint, NSE & Google News RSS...")
            
            all_nse_symbols = tick_helper.get_all_nse_tickers()
            
            # Fetch from ALL sources concurrently
            scraped_items = news_helper.fetch_news_from_all_sources(all_symbols=all_nse_symbols, max_items=50)
            
            status.write(f"✅ Fetched {len(scraped_items)} raw news items from all sources")
            status.write("🔍 Matching tickers and categorizing catalysts...")
            
            # Process and categorize
            processed_news = news_helper.scrape_live_all_nse_news_from_items(scraped_items, all_nse_symbols)
            
            status.write(f"📊 Processed {len(processed_news)} news picks with ticker matches")
            
            # ── NEW: Compute ATR-based trade recommendations for ticker-matched items ──
            status.write("💰 Computing swing trade levels (Price/SL/Target) for ticker-matched news...")
            
            # We need to get the data_cache. Download data on-the-fly for any news tickers
            news_tickers = list(set(
                n.get("Symbol") or n.get("Ticker") or "" for n in processed_news
                if n.get("Symbol") or n.get("Ticker")
            ))
            
            data_cache_for_news = {}
            if news_tickers:
                import data_provider as dp
                # Try loading from existing session data_cache first
                if st.session_state.data_cache:
                    for t in news_tickers:
                        if t in st.session_state.data_cache:
                            data_cache_for_news[t] = st.session_state.data_cache[t]
                
                # Fetch any missing tickers
                missing_tickers = [t for t in news_tickers if t not in data_cache_for_news]
                if missing_tickers:
                    try:
                        batch_data = dp.download_stock_data_batch(missing_tickers, period="1y")
                        data_cache_for_news.update(batch_data)
                    except Exception as batch_err:
                        print(f"Error fetching batch data for news: {batch_err}")
            
            # Load existing picks from cache for delta computation
            import json, os
            existing_news_list = []
            if os.path.exists("news_cache.json"):
                try:
                    with open("news_cache.json", "r", encoding="utf-8") as f:
                        existing_news_list = json.load(f)
                except Exception:
                    pass
            
            # Compute full recommendations with trade levels
            news_with_recs = news_helper.get_today_news_recommendations(
                data_cache_for_news,
                all_symbols=all_nse_symbols,
                existing_picks=existing_news_list
            )
            
            status.write(f"✅ Computed trade levels for {len(news_with_recs)} news items")
            
            # Update session state with full recommendations (has Price/SL/Target/Type)
            st.session_state.news_picks = pd.DataFrame(news_with_recs) if news_with_recs else pd.DataFrame()
            
            # Save to cache (merge with full recommendation data)
            try:
                existing_map = {}
                if os.path.exists("news_cache.json"):
                    with open("news_cache.json", "r", encoding="utf-8") as _f:
                        for _item in json.load(_f):
                            existing_map[_item.get("Headline", "")] = _item
                
                for _p in news_with_recs:
                    existing_map[_p.get("Headline", "")] = _p
                
                merged = list(existing_map.values())
                try:
                    merged = news_helper.prune_cache_by_days(merged, days=30, date_key='Date')
                except Exception:
                    pass
                with open("news_cache.json", "w", encoding="utf-8") as _f:
                    json.dump(merged, _f, indent=2, ensure_ascii=False)
            except Exception as cache_err:
                print(f"Cache save error: {cache_err}")
            
            status.update(label=f"✅ Loaded {len(news_with_recs)} news items with trade recommendations", state="complete", expanded=False)
        
        st.toast(f"📰 Loaded {len(news_with_recs)} news items with trade levels", icon="📰")
        st.rerun()
    except Exception as load_err:
        print(f"Full news load error: {load_err}")
        st.toast("⚠️ Full news load failed - check console", icon="⚠️")

if run_full_btn:
    st.session_state.is_analyzing = False
    try:
        raw = _resolve_universe_tickers(stock_universe, custom_tickers)
        if not raw:
            st.error("No tickers resolved. Please check your selection.")
            st.stop()
        
        # Force include news pick symbols
        try:
            live_news_list = news_helper.get_live_news_picks()
            for sym in ([n["Symbol"] for n in live_news_list] +
                        [n["Symbol"] for n in news_helper.HISTORICAL_NEWS_CATALYSTS]):
                if sym and sym not in raw:
                    raw.append(sym)
        except Exception:
            pass
        
        st.session_state.is_analyzing = True
        st.session_state.analysis_universe = raw
        st.session_state.analysis_mode = "full"
        st.session_state.analysis_index = 0
        st.session_state.accumulated_matching = []
        st.session_state.accumulated_past_sigs = []
        st.session_state.accumulated_medium_term = []
        st.session_state.accumulated_intraday_picks = []
        st.session_state.accumulated_intraday_backtest = []
        st.session_state.accumulated_data_cache = {}
        st.session_state.accumulated_ltp_cache = {}
        st.session_state.bulk_deals_cached = None
        st.session_state.screener_results = pd.DataFrame()
        st.session_state.past_signals_results = pd.DataFrame()
        st.session_state.medium_term_picks = pd.DataFrame()
        st.session_state.intraday_picks = pd.DataFrame()
        st.session_state.intraday_backtest = pd.DataFrame()
        st.session_state.screened_universe = stock_universe
        st.session_state.screened_strategy = selected_strategy
        st.session_state.last_run_time = "Starting..."
        st.session_state.last_sync_time = "Starting..."
        st.session_state.last_sync_timestamp = time.time()
        
        _start_background_analysis(raw, selected_strategy, min_price, min_vol_ratio, mode="full")
        st.rerun()
    except Exception as e:
        st.error(f"Full analysis failed: {e}")
        st.session_state.is_analyzing = False

# ─────────────────────────────────────────────────────────────────────────────
# Progressive Analysis Runner Block
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.get("is_analyzing"):
    worker_state = _get_analysis_worker_state()
    if worker_state:
        _sync_worker_state_to_session(worker_state)
        st.session_state.analysis_last_refresh_ts = time.time()
    else:
        # Ensure progress shows 0 if worker state not yet available
        if st.session_state.get("analysis_index") is None:
            st.session_state.analysis_index = 0

    now = time.time()
    last_refresh = st.session_state.get("analysis_last_refresh_ts", 0.0)

    if worker_state and worker_state.get("done"):
        st.session_state.is_analyzing = False
        if worker_state.get("error"):
            st.toast(f"⚠️ Scan stopped: {worker_state['error']}", icon="⚠️")
        else:
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            st.session_state.last_run_time = now_str
            st.session_state.last_sync_time = now_str
            st.session_state.last_sync_timestamp = time.time()
            st.toast("✅ Full Progressive Scan Completed Successfully!", icon="📈")
            
            # --- ADD TO GLOBAL HISTORY CACHE ---
            try:
                if st.session_state.get("analysis_mode") == "full":
                    all_picks = []
                    
                    if st.session_state.screener_results is not None and not st.session_state.screener_results.empty:
                        swing = st.session_state.screener_results.to_dict(orient="records")
                        for p in swing:
                            p["Source"] = "swing"
                            all_picks.append(p)
                            
                    if st.session_state.medium_term_picks is not None and not st.session_state.medium_term_picks.empty:
                        med = st.session_state.medium_term_picks.to_dict(orient="records")
                        for p in med:
                            p["Source"] = "medium"
                            all_picks.append(p)
                            
                    if st.session_state.intraday_picks is not None and not st.session_state.intraday_picks.empty:
                        intra_p = st.session_state.intraday_picks.to_dict(orient="records")
                        for p in intra_p:
                            p["Source"] = "intraday"
                            all_picks.append(p)

                    if st.session_state.news_picks is not None and not st.session_state.news_picks.empty:
                        news_p = st.session_state.news_picks.to_dict(orient="records")
                        for p in news_p:
                            p["Source"] = "news"
                            all_picks.append(p)

                    date_str = datetime.date.today().isoformat()
                    uni = st.session_state.screened_universe
                    strat = st.session_state.screened_strategy
                    
                    cache = hist.load_history_cache()
                    hist.add_run_to_history(cache, date_str, uni, strat, "manual_full", all_picks)
            except Exception as hist_e:
                print(f"Error saving to global cache: {hist_e}")
            # -------------------------------------
            
        st.rerun()
    elif worker_state and not worker_state.get("done"):
        # Force the page to refresh while the background analysis is still running.
        # This keeps the batch progress display updated even if auto-refresh JS is blocked.
        if now - last_refresh >= 0.5:
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CONTENT — only rendered after at least one run
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.screener_results is not None or st.session_state.news_picks is not None:

    # ── FAST LIVE SYNC (Background) ──
    current_time = time.time()
    
    if auto_refresh and (current_time - st.session_state.last_sync_timestamp >= 60.0):
        # We perform a fast update
        # 1. Gather all active tickers across picks
        active_tickers = set()
        for frame in [
            st.session_state.screener_results,
            st.session_state.medium_term_picks,
            st.session_state.news_picks,
            st.session_state.intraday_picks,
        ]:
            normalized = _ensure_ticker_column(frame)
            if normalized is not None and not normalized.empty:
                active_tickers.update([str(v).strip() for v in normalized["Ticker"].tolist() if str(v).strip()])
            
        active_tickers = list(active_tickers)
        
        # 2. Update LTP cache in batch
        if active_tickers:
            updated_ltp = _get_ltp_cache(active_tickers, st.session_state.data_cache)
            if st.session_state.ltp_cache is None:
                st.session_state.ltp_cache = {}
            st.session_state.ltp_cache.update(updated_ltp)
            
        # 3. Update news catalysts recommendations (Throttled to 20 seconds and written to local cache)
        if st.session_state.data_cache and (current_time - st.session_state.last_news_scrape_timestamp >= 60.0):
            try:
                all_nse_symbols = tick_helper.get_all_nse_tickers()
                existing_news_list = []
                if os.path.exists("news_cache.json"):
                    try:
                        with open("news_cache.json", "r", encoding="utf-8") as f:
                            existing_news_list = json.load(f)
                    except Exception:
                        pass
                latest_news = news_helper.get_today_news_recommendations(st.session_state.data_cache, all_symbols=all_nse_symbols, existing_picks=existing_news_list)
                st.session_state.news_picks = pd.DataFrame(latest_news) if latest_news else pd.DataFrame()
                
                # Save background news (MERGE to preserve earlier news from the day)
                try:
                    existing_map = {}
                    if os.path.exists("news_cache.json"):
                        with open("news_cache.json", "r", encoding="utf-8") as _f:
                            for _item in json.load(_f):
                                existing_map[_item.get("Headline", "")] = _item
                    for _p in latest_news:
                        existing_map[_p.get("Headline", "")] = _p
                    # Preserve full history when saving background updates
                    merged = list(existing_map.values())
                    try:
                        merged = news_helper.prune_cache_by_days(merged, days=30, date_key='Date')
                    except Exception:
                        pass
                    with open("news_cache.json", "w", encoding="utf-8") as _f:
                        json.dump(merged, _f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"Error saving background news to local cache: {e}")
                    
                st.session_state.last_news_scrape_timestamp = current_time
            except Exception as e:
                print(f"Error refreshing news in background: {e}")
                
        # 4. Update sync timestamps
        st.session_state.last_sync_time = datetime.datetime.now().strftime("%H:%M:%S")
        st.session_state.last_sync_timestamp = current_time

    # ── PROGRESSIVE SCAN STATUS BAR ──
    if st.session_state.get("is_analyzing"):
        total = len(st.session_state.analysis_universe)
        idx = st.session_state.analysis_index
        progress_pct = min(idx / total, 1.0) if total else 0.0
        batch_label = st.session_state.get("analysis_batch", 0)
        total_batches = st.session_state.get("analysis_total_batches", 0)
        status_label = st.session_state.get("analysis_status", "Preparing batch...")
        st.markdown(f"""
        <div style="background: rgba(0, 102, 204, 0.08); border: 1px solid rgba(0, 102, 204, 0.22); padding: 14px 20px; border-radius: 8px; margin-bottom: 12px; position: relative; overflow: hidden;">
            <div class="ford-scan-line"></div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div>
                    <span class="live-dot"></span>
                    <span style="font-size: 0.72rem; color: #5a7a9a; letter-spacing: 0.08em; font-weight: 700; text-transform: uppercase;">SCANNING IN PROGRESS...</span>
                    <h3 style="margin: 4px 0 0; font-size: 1rem; color: #dde5f0;">⚡ {status_label} on {st.session_state.screened_universe} using {st.session_state.screened_strategy}...</h3>
                </div>
                <div style="text-align: right;">
                    <span style="font-family: 'JetBrains Mono', monospace; font-size: 1.15rem; font-weight: 700; color: #0080ff;">{idx}/{total} Stocks ({progress_pct*100:.0f}%)</span>
                    <div style="font-size: 0.72rem; color: #5a7a9a; margin-top: 4px;">Batch {batch_label}/{total_batches}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.progress(progress_pct)
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # ── FORD SYSTEM MONITOR STATUS BAR ──
    last_run  = st.session_state.get("last_run_time", "—")
    last_sync = st.session_state.get("last_sync_time", "—")
    news_last = st.session_state.get("last_news_scrape_timestamp", 0.0)
    news_ago  = int(time.time() - news_last) if news_last else 0
    news_ago_str = f"{news_ago}s ago" if news_last else "Pending"
    data_cnt  = len(st.session_state.data_cache or {})
    news_cnt  = len(st.session_state.news_picks) if st.session_state.news_picks is not None and not st.session_state.get("news_picks", pd.DataFrame()).empty else 0

    st.markdown(
        f'<div class="ford-monitor">'
        f'<span class="ford-monitor-label">⚡ System Monitor</span>'
        f'<div style="display:flex;gap:22px;flex-wrap:wrap;">'
        f'<span class="ford-monitor-item">Full Scan: <span class="ford-monitor-value">{last_run}</span></span>'
        f'<span class="ford-monitor-item">Live Sync: <span class="ford-monitor-good">{last_sync}</span></span>'
        f'<span class="ford-monitor-item">News Refresh: <span class="ford-monitor-value">{news_ago_str}</span></span>'
        f'<span class="ford-monitor-item">Stocks Loaded: <span class="ford-monitor-value">{data_cnt}</span></span>'
        f'<span class="ford-monitor-item">News Picks: <span class="ford-monitor-value">{news_cnt}</span></span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    results_df = _ensure_ticker_column(st.session_state.screener_results if st.session_state.screener_results is not None else pd.DataFrame())
    past_df    = _ensure_ticker_column(st.session_state.past_signals_results if st.session_state.past_signals_results is not None else pd.DataFrame())
    data_cache = st.session_state.data_cache or {}
    ltp_cache  = st.session_state.ltp_cache or {}
    news_df_session = _ensure_ticker_column(st.session_state.news_picks if st.session_state.news_picks is not None else pd.DataFrame())
    medium_df_session = _ensure_ticker_column(st.session_state.medium_term_picks if st.session_state.medium_term_picks is not None else pd.DataFrame())
    intra_df_session = _ensure_ticker_column(st.session_state.intraday_picks if st.session_state.intraday_picks is not None else pd.DataFrame())

    tab1, tab2_intra, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "⚡  Live Picks & Prices",
        "🏃  Intraday Scanner",
        "📰  News Catalyst Scanner",
        "📊  Backtest Tracker",
        "🔍  Chart Analysis",
        "⚙️  3-Month Multi-Strategy Optimizer",
        "📜  Analysis History",
    ])

    # ══════════════════════════════════════════════════════════════
    # TAB 1 — Today's picks with live price cards
    # ══════════════════════════════════════════════════════════════
    with tab1:
        universe_l = st.session_state.screened_universe or "—"
        strategy_l = st.session_state.screened_strategy or "—"
        st.markdown(
            f'<div class="infobox"><b>Universe:</b> {universe_l} &nbsp;·&nbsp; '
            f'<b>Strategy:</b> {strategy_l} &nbsp;·&nbsp; '
            f'<b>Matched:</b> {len(results_df)} stocks &nbsp;·&nbsp; '
            f'<span style="color:#3fb950;font-weight:700;">● Live prices via NSE API</span></div>',
            unsafe_allow_html=True,
        )

        if results_df.empty:
            st.warning("No stocks matched. Try a wider universe or lower filters.")
        else:
            nifty50_syms = {s.replace(".NS", "").upper() for s in tick_helper.get_nifty50_tickers()}

            conv_95_mask = (results_df["Strategy"] == "High-Conviction 95% Pullback")
            opt_mask  = (
                results_df["Ticker"].str.replace(".NS", "").str.upper().isin(nifty50_syms) &
                results_df["Strategy"].isin([
                    "EMA Pullback (20)", "MACD Crossover",
                    "RSI Pullback (Uptrend)", "RSI Reversal (Oversold)"
                ])
            )
            conv_95_df = results_df[conv_95_mask].copy()
            opt_df  = results_df[opt_mask & ~conv_95_mask].copy()
            hi_df   = results_df[~opt_mask & ~conv_95_mask &  (results_df["High_Conviction"] == True)].copy()
            tech_df = results_df[~opt_mask & ~conv_95_mask & ~(results_df["High_Conviction"] == True)].copy()

        # — 🎯 Tier-0 95%+ Win-Rate Conviction Pullbacks —
        _sec_header("🎯", "Tier-0 — 95%+ Win-Rate Conviction Pullbacks",
                    count=len(conv_95_df) if not results_df.empty else 0, badge="95%+ Success Rate Strategy")
        if not results_df.empty:
            _render_cards(conv_95_df, ltp_cache)

        # — A. Optimised Focus Group —
        _sec_header("🏆", "Optimized Focus Group — Nifty 50 Pullbacks & Reversals",
                    count=len(opt_df) if not results_df.empty else 0, badge="78%+ Win Rate")
        if not results_df.empty:
            _render_cards(opt_df, ltp_cache)

        # — B. Tier-1 Institutional —
        _sec_header("💎", "Tier-1 — Institutional + Technical Confluence",
                    count=len(hi_df) if not results_df.empty else 0, badge="FII / MF Backed")
        if not results_df.empty:
            _render_cards(hi_df, ltp_cache)

        # — C. Tier-2 Technical —
        _sec_header("📈", "Tier-2 — Technical Momentum Setups",
                    count=len(tech_df) if not results_df.empty else 0)
        if not results_df.empty:
            _render_cards(tech_df, ltp_cache)



        # — E. Medium-Term —
        mt_df  = medium_df_session
        mt_cnt = len(mt_df) if (mt_df is not None and not mt_df.empty) else 0
        _sec_header("🚀", "Medium-Term Swing — 15 Days to 1 Month Hold",
                    count=mt_cnt, badge="EMA Cross · BB Squeeze")
        _render_cards(mt_df, ltp_cache, card_type="medium")

        # Export
        if not results_df.empty:
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            st.download_button(
                "📥  Export Picks (CSV)",
                data=results_df.to_csv(index=False).encode(),
                file_name=f"nse_pulse_{datetime.date.today()}.csv",
                mime="text/csv",
            )

    # ══════════════════════════════════════════════════════════════
    # TAB 2 — Intraday Scanner (BUY-SELL & SELL-BUY)
    # ══════════════════════════════════════════════════════════════
    with tab2_intra:
        st.markdown("""
        <div class="infobox">
          <b>🏃 Real-Time Intraday Momentum Scanner & Backtester (Same-Day to Next-Day Hold)</b><br>
          Monitors technical setups optimized for high-liquidity active stocks. Supports both 
          <b>Buy-Sell (Long)</b> momentum plays and <b>Sell-Buy (Short)</b> setups with reversed stop loss/target order tracking.
        </div>
        """, unsafe_allow_html=True)

        intra_df = intra_df_session
        intra_bt = st.session_state.intraday_backtest

        if intra_df is None or intra_df.empty:
            st.markdown('<div class="infobox">No intraday setups loaded. Select stock universe and click "Run Full Analysis" in the sidebar to scan.</div>', unsafe_allow_html=True)
        else:
            longs = intra_df[intra_df["Type"] == "BUY-SELL"].copy()
            shorts = intra_df[intra_df["Type"] == "SELL-BUY"].copy()

            # Long Setups
            _sec_header("🟢", "Intraday BUY-SELL (Long) Setups", count=len(longs))
            _render_cards(longs, ltp_cache)

            # Short Setups
            _sec_header("🔴", "Intraday SELL-BUY (Short) Setups", count=len(shorts))
            _render_cards(shorts, ltp_cache)

            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
            st.markdown("### 📋 Active Intraday Setups Table")
            show_intra = intra_df[["Ticker", "Strategy", "Type", "Price", "Entry Range", "Target", "Stop Loss", "RSI", "Vol_Ratio", "Reason"]].copy()
            # Coerce numeric columns to prevent PyArrow serialization ArrowTypeError
            for numeric_col in ["Price", "Target", "Stop Loss", "RSI", "Vol_Ratio"]:
                if numeric_col in show_intra.columns:
                    show_intra[numeric_col] = pd.to_numeric(show_intra[numeric_col], errors='coerce')
            st.dataframe(
                show_intra,
                column_config={
                    "Price": st.column_config.NumberColumn("CMP (₹)", format="₹%.2f"),
                    "Target": st.column_config.NumberColumn("Target (₹)", format="₹%.2f"),
                    "Stop Loss": st.column_config.NumberColumn("Stop Loss (₹)", format="₹%.2f"),
                    "Vol_Ratio": st.column_config.NumberColumn("Vol Ratio", format="%.2f×"),
                    "RSI": st.column_config.NumberColumn("RSI", format="%.1f"),
                },
                hide_index=True,
                width='stretch'
            )

            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            st.download_button(
                "📥 Export Intraday Picks (CSV)",
                data=intra_df.to_csv(index=False).encode(),
                file_name=f"intraday_picks_{datetime.date.today()}.csv",
                mime="text/csv",
                key="download_intraday_picks_csv"
            )

        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        st.markdown("### 📈 Intraday Performance Log (Last 10 Trading Days)")
        
        if intra_bt is not None and not intra_bt.empty:
            # Stats metrics
            hits = len(intra_bt[intra_bt["Status"] == "Target Hit"])
            losses = len(intra_bt[intra_bt["Status"] == "Stop Loss Hit"])
            times = len(intra_bt[intra_bt["Status"] == "Time Exit"])
            wr = hits / (hits + losses) * 100 if (hits + losses) > 0 else 0.0

            mc1, mc2, mc3, mc4 = st.columns(4)
            with mc1:
                st.metric("Total Trades", len(intra_bt))
            with mc2:
                st.metric("🟢 Target Hit", hits)
            with mc3:
                st.metric("🔴 Stop Loss Hit", losses)
            with mc4:
                st.metric("Win Rate", f"{wr:.1f}%" if (hits + losses) > 0 else "N/A")

            # Trade table
            _bt_table(intra_bt, extra_cols=["Type"])
        else:
            st.markdown('<div class="infobox">No historical intraday backtests found. Run Analysis first.</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    # TAB 3 — News Catalyst Scanner
    # ══════════════════════════════════════════════════════════════
    with tab2:
        st.markdown("""
        <div class="infobox">
          <b>📰 Real-Time News Catalyst Scanner & Swing Trade Picker</b><br>
          Monitors live Google News RSS and corporate announcements across <b>all NSE stocks</b>.
          Headlines are scanned for technical catalysts (order wins, earnings beats, M&A) and 
          swing trade entry/target/SL levels are computed dynamically on-the-fly.
        </div>
        """, unsafe_allow_html=True)

        news_df = news_df_session
        if news_df is not None and not news_df.empty:
            news_df = pd.DataFrame(news_helper.sort_news_items(news_df.to_dict("records")))
            news_df = _ensure_ticker_column(news_df)
        news_cnt = len(news_df) if (news_df is not None and not news_df.empty) else 0
        news_bt_df = st.session_state.news_past_results
        
        if news_bt_df is not None and not news_bt_df.empty:
            hits = len(news_bt_df[news_bt_df["Status"] == "Target Hit"])
            losses = len(news_bt_df[news_bt_df["Status"] == "Stop Loss Hit"])
            news_wr = hits / (hits + losses) * 100 if (hits + losses) > 0 else 0.0
        else:
            news_wr = 0.0

        # Metric Cards
        nc1, nc2, nc3 = st.columns(3)
        with nc1:
            st.metric("Today's News Picks", news_cnt)
        with nc2:
            st.metric("Historical Win Rate (News)", f"{news_wr:.1f}%" if news_bt_df is not None and not news_bt_df.empty else "N/A")
        with nc3:
            st.metric("Coverage", "All NSE Stocks", delta="Live RSS Scraped")

        # Live news cards
        _sec_header("🔥", "Live Catalyst Picks — Swing Trade Setups", count=news_cnt)
        if news_df is not None and not news_df.empty:
            _render_cards(news_df, ltp_cache, card_type="news")
            
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
            st.markdown("### 📋 News Trade Setups Table")
            desired_news_cols = ["Ticker", "DateTime", "Headline", "Catalyst", "Price", "Entry Range", "Target", "Stop Loss", "Sentiment"]
            show_news = pd.DataFrame()
            for col in desired_news_cols:
                if col in news_df.columns:
                    show_news[col] = news_df[col]
                else:
                    show_news[col] = ""
            # Coerce numeric columns to prevent PyArrow serialization ArrowTypeError
            for numeric_col in ["Price", "Target", "Stop Loss"]:
                if numeric_col in show_news.columns:
                    show_news[numeric_col] = pd.to_numeric(show_news[numeric_col], errors='coerce')
            st.dataframe(
                show_news,
                column_config={
                    "DateTime": st.column_config.TextColumn("Date/Time"),
                    "Price": st.column_config.NumberColumn("Current Price (₹)", format="₹%.2f"),
                    "Target": st.column_config.NumberColumn("Target (₹)", format="₹%.2f"),
                    "Stop Loss": st.column_config.NumberColumn("SL (₹)", format="₹%.2f"),
                },
                hide_index=True,
                width='stretch'
            )
            
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            st.download_button(
                "📥 Export News Picks (CSV)",
                data=news_df.to_csv(index=False).encode(),
                file_name=f"news_picks_{datetime.date.today()}.csv",
                mime="text/csv",
                key="download_news_picks_csv"
            )
        else:
            st.markdown('<div class="infobox">No news picks matched today. Click "Run Full Analysis" to trigger news scan.</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        st.markdown("### 📈 Historical News Performance (Last 10 Trading Days)")
        
        if news_bt_df is not None and not news_bt_df.empty:
            _bt_table(news_bt_df, extra_cols=["Catalyst", "Headline"])
            _bt_stats(news_bt_df)
        else:
            st.markdown('<div class="infobox">No historical news trades in log. Run Analysis to load news backtest.</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    # TAB 3 — Backtest tracker
    # ══════════════════════════════════════════════════════════════
    with tab3:
        _dir = os.path.dirname(os.path.abspath(__file__))

        # A. Optimised Focus Group
        _sec_header("🏆", "Optimized Focus Group — Last 10 Trading Days")
        opt_cache = os.path.join(_dir, "opt_backtest_cache.csv")
        if os.path.exists(opt_cache):
            try:
                _df = pd.read_csv(opt_cache)
                _bt_table(_df)
                _bt_stats(_df)
            except Exception as e:
                st.error(f"Error loading cache: {e}")
        else:
            st.markdown('<div class="infobox">Run Analysis to generate backtest cache.</div>',
                        unsafe_allow_html=True)

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        # B. Tier-1 High-Conviction
        _sec_header("💎", "Tier-1 High-Conviction — Last 10 Trading Days")
        t1_cache = os.path.join(_dir, "t1_backtest_cache.csv")
        if os.path.exists(t1_cache):
            try:
                _df = pd.read_csv(t1_cache)
                _bt_table(_df, extra_cols=["Institutional_Details"])
                _bt_stats(_df)
            except Exception as e:
                st.error(f"Error loading cache: {e}")
        else:
            st.markdown('<div class="infobox">Run Analysis to generate backtest cache.</div>',
                        unsafe_allow_html=True)

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        # Tier-0 — 95%+ Win-Rate Conviction Pullbacks (live from session)
        t0_past = past_df[past_df["Strategy"] == "High-Conviction 95% Pullback"] if past_df is not None and not past_df.empty else pd.DataFrame()
        _sec_header("🎯", "Tier-0 — 95%+ Win-Rate Conviction Pullbacks — Last 5 Trading Days",
                    count=len(t0_past))
        _bt_table(t0_past)
        _bt_stats(t0_past)

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        # C. Tier-2 Technical (live from session)
        t2_past = past_df[past_df["Strategy"] != "High-Conviction 95% Pullback"] if past_df is not None and not past_df.empty else pd.DataFrame()
        _sec_header("📈", "Tier-2 Technical — Last 5 Trading Days",
                    count=len(t2_past))
        _bt_table(t2_past)
        _bt_stats(t2_past)



        # E. Medium-Term 2-Month
        _sec_header("🚀", "Medium-Term Swing — Last 2 Months")
        lt_cache = os.path.join(_dir, "long_term_backtest_cache.csv")
        if os.path.exists(lt_cache):
            try:
                _df = pd.read_csv(lt_cache)
                _bt_table(_df, extra_cols=["High_Conviction"])
                _bt_stats(_df)
            except Exception as e:
                st.error(f"Error loading cache: {e}")
        else:
            st.markdown('<div class="infobox">Run Analysis to generate cache.</div>',
                        unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    # TAB 3 — Deep chart analysis
    # ══════════════════════════════════════════════════════════════
    with tab4:
        # Gather all ticker options
        all_syms = list(dict.fromkeys(
            (results_df["Ticker"].tolist() if not results_df.empty else []) +
            (news_df_session["Ticker"].tolist()
             if news_df_session is not None and not news_df_session.empty else []) +
            (medium_df_session["Ticker"].tolist()
             if medium_df_session is not None and not medium_df_session.empty else [])
        ))

        if not all_syms:
            st.markdown('<div class="infobox">No picks available. Run Analysis first.</div>',
                        unsafe_allow_html=True)
        else:
            selected_ticker = st.selectbox(
                "Select stock for detailed chart",
                options=all_syms,
                format_func=lambda x: x.replace(".NS", ""),
            )

            if selected_ticker and selected_ticker in data_cache:
                hist_df = data_cache[selected_ticker]
                symbol  = selected_ticker.replace(".NS", "")

                # Live price
                ltp    = ltp_cache.get(selected_ticker) or dp.get_live_ltp(symbol)
                pclose = float(hist_df['Close'].iloc[-2]) if len(hist_df) > 1 else float(hist_df['Close'].iloc[-1])
                if not ltp:
                    ltp = float(hist_df['Close'].iloc[-1])
                chg_pct   = (ltp - pclose) / pclose * 100 if pclose else 0.0
                ltp_color = "#3fb950" if chg_pct >= 0 else "#f85149"
                arrow     = "▲" if chg_pct >= 0 else "▼"

                df_ind  = scr.calculate_indicators(hist_df)
                if df_ind is None:
                    st.warning("Insufficient data for this stock.")
                else:
                    plot_df = df_ind.tail(120).copy()
                    r       = df_ind.iloc[-1]
                    rsi_c   = "#f85149" if r['RSI'] > 70 else "#3fb950" if r['RSI'] < 30 else "#e6edf3"
                    rsi_lbl = "Overbought" if r['RSI'] > 70 else "Oversold" if r['RSI'] < 30 else "Neutral"
                    vol_c   = "#d2a8ff" if r['Vol_Ratio'] >= 1.5 else "#e6edf3"
                    vwap_c  = "#3fb950" if ltp >= r['VWAP'] else "#f85149"
                    vwap_lbl= f"{'Above' if ltp>=r['VWAP'] else 'Below'} VWAP"
                    h52     = r.get("High52W", ltp)
                    l52     = r.get("Low52W", ltp)
                    pct52   = (ltp / h52 * 100) if h52 else 0.0

                    # Live banner
                    st.markdown(f"""
                    <div class="live-banner">
                      <div class="lb-item" style="min-width:80px;">
                        <div class="lb-label">Symbol</div>
                        <div style="font-size:1.35rem;font-weight:800;color:#e6edf3;">{symbol}</div>
                        <div class="lb-sub">NSE · Equity</div>
                      </div>
                      <div class="lb-divider"></div>
                      <div class="lb-item">
                        <div class="lb-label"><span class="live-dot"></span>Live Price</div>
                        <div class="lb-value" style="color:{ltp_color};font-size:1.35rem;">₹{ltp:,.2f}</div>
                        <div class="lb-sub" style="color:{ltp_color};">{arrow} {abs(chg_pct):.2f}%</div>
                      </div>
                      <div class="lb-divider"></div>
                      <div class="lb-item">
                        <div class="lb-label">52W Range</div>
                        <div class="lb-value" style="font-size:.92rem;">₹{l52:,.0f} – ₹{h52:,.0f}</div>
                        <div class="lb-sub">At {pct52:.1f}% of 52W High</div>
                      </div>
                      <div class="lb-divider"></div>
                      <div class="lb-item">
                        <div class="lb-label">RSI (14)</div>
                        <div class="lb-value" style="color:{rsi_c};">{r['RSI']:.1f}</div>
                        <div class="lb-sub">{rsi_lbl}</div>
                      </div>
                      <div class="lb-divider"></div>
                      <div class="lb-item">
                        <div class="lb-label">VWAP</div>
                        <div class="lb-value" style="color:{vwap_c};">₹{r['VWAP']:,.2f}</div>
                        <div class="lb-sub">{vwap_lbl}</div>
                      </div>
                      <div class="lb-divider"></div>
                      <div class="lb-item">
                        <div class="lb-label">Vol Ratio</div>
                        <div class="lb-value" style="color:{vol_c};">{r['Vol_Ratio']:.2f}×</div>
                        <div class="lb-sub">vs 20-day avg</div>
                      </div>
                      <div class="lb-divider"></div>
                      <div class="lb-item">
                        <div class="lb-label">ATR (14)</div>
                        <div class="lb-value">₹{r['ATR']:.2f}</div>
                        <div class="lb-sub">Daily volatility</div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # ── 4-panel chart ──
                    fig = make_subplots(
                        rows=4, cols=1, shared_xaxes=True,
                        vertical_spacing=0.022,
                        row_heights=[0.52, 0.16, 0.16, 0.16],
                        subplot_titles=[
                            f"{symbol} — 120-Day Daily Chart",
                            "Volume", "RSI (14)", "MACD (12, 26, 9)"
                        ],
                    )

                    # Candlestick
                    fig.add_trace(go.Candlestick(
                        x=plot_df.index,
                        open=plot_df['Open'], high=plot_df['High'],
                        low=plot_df['Low'],   close=plot_df['Close'],
                        name="Candles",
                        increasing_line_color="#3fb950",
                        increasing_fillcolor="rgba(63,185,80,0.85)",
                        decreasing_line_color="#f85149",
                        decreasing_fillcolor="rgba(248,81,73,0.85)",
                    ), row=1, col=1)

                    # EMAs
                    for ema, col_c, dash in [
                        ("EMA20",  "#58a6ff", "solid"),
                        ("EMA50",  "#ffa657", "solid"),
                        ("EMA200", "#f778ba", "dot"),
                    ]:
                        fig.add_trace(go.Scatter(
                            x=plot_df.index, y=plot_df[ema], name=ema,
                            line=dict(color=col_c, width=1.5, dash=dash),
                        ), row=1, col=1)

                    # VWAP
                    fig.add_trace(go.Scatter(
                        x=plot_df.index, y=plot_df['VWAP'], name="VWAP",
                        line=dict(color="#d2a8ff", width=1.5, dash="dash"),
                    ), row=1, col=1)

                    # Bollinger Bands
                    fig.add_trace(go.Scatter(
                        x=plot_df.index, y=plot_df['BB_Upper'], name="BB Upper",
                        line=dict(color="rgba(63,185,80,.2)", width=1, dash="dash"),
                        showlegend=False,
                    ), row=1, col=1)
                    fig.add_trace(go.Scatter(
                        x=plot_df.index, y=plot_df['BB_Lower'], name="BB Lower",
                        line=dict(color="rgba(248,81,73,.2)", width=1, dash="dash"),
                        fill="tonexty", fillcolor="rgba(255,255,255,.018)",
                        showlegend=False,
                    ), row=1, col=1)

                    # LTP reference line
                    fig.add_hline(
                        y=ltp, line_dash="dot", line_color=ltp_color, line_width=1.5,
                        annotation_text=f"LTP ₹{ltp:,.2f}",
                        annotation_font_color=ltp_color,
                        annotation_font_size=11,
                        row=1, col=1,
                    )

                    # Volume
                    v_colors = [
                        "rgba(248,81,73,.7)" if plot_df['Close'].iloc[i] < plot_df['Open'].iloc[i]
                        else "rgba(63,185,80,.7)"
                        for i in range(len(plot_df))
                    ]
                    fig.add_trace(go.Bar(
                        x=plot_df.index, y=plot_df['Volume'],
                        name="Volume", marker_color=v_colors, showlegend=False,
                    ), row=2, col=1)
                    fig.add_trace(go.Scatter(
                        x=plot_df.index, y=plot_df['Vol_Avg20'], name="Vol 20D",
                        line=dict(color="#6e7f96", width=1.2, dash="dot"), showlegend=False,
                    ), row=2, col=1)

                    # RSI
                    fig.add_trace(go.Scatter(
                        x=plot_df.index, y=plot_df['RSI'], name="RSI",
                        line=dict(color="#79c0ff", width=1.5), showlegend=False,
                        fill="tozeroy", fillcolor="rgba(121,192,255,.04)",
                    ), row=3, col=1)
                    for y_lvl, lc in [(70, "#f85149"), (30, "#3fb950"), (50, "#4a5568")]:
                        fig.add_hline(y=y_lvl, line_dash="dash", line_color=lc,
                                      line_width=1, row=3, col=1)

                    # MACD
                    hist_c = [
                        "rgba(63,185,80,.7)" if v >= 0 else "rgba(248,81,73,.7)"
                        for v in plot_df['MACD_Hist']
                    ]
                    fig.add_trace(go.Bar(
                        x=plot_df.index, y=plot_df['MACD_Hist'],
                        name="MACD Hist", marker_color=hist_c, showlegend=False,
                    ), row=4, col=1)
                    fig.add_trace(go.Scatter(
                        x=plot_df.index, y=plot_df['MACD'], name="MACD",
                        line=dict(color="#58a6ff", width=1.3), showlegend=False,
                    ), row=4, col=1)
                    fig.add_trace(go.Scatter(
                        x=plot_df.index, y=plot_df['MACD_Signal'], name="Signal",
                        line=dict(color="#ffa657", width=1.3), showlegend=False,
                    ), row=4, col=1)

                    fig.update_layout(
                        height=820,
                        xaxis_rangeslider_visible=False,
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#8892a4", family="Inter", size=11),
                        margin=dict(t=42, b=16, l=10, r=10),
                        legend=dict(
                            bgcolor="rgba(13,17,23,.9)",
                            bordercolor="#21262d", borderwidth=1,
                            font=dict(size=10),
                            orientation="h",
                            yanchor="bottom", y=1.01,
                            xanchor="left",   x=0,
                        ),
                    )
                    fig.update_xaxes(
                        showgrid=True, gridcolor="rgba(255,255,255,.04)", gridwidth=1,
                        showspikes=True, spikecolor="#1f6feb", spikethickness=1,
                    )
                    fig.update_yaxes(
                        showgrid=True, gridcolor="rgba(255,255,255,.04)", gridwidth=1,
                    )
                    st.plotly_chart(fig, width='stretch')

                    # ── Trade setup detail cards ──
                    selected_row = None
                    normalized_results = _ensure_ticker_column(results_df)
                    normalized_news = _ensure_ticker_column(st.session_state.news_picks)
                    normalized_medium = _ensure_ticker_column(st.session_state.medium_term_picks)

                    if not normalized_results.empty and selected_ticker in normalized_results["Ticker"].values:
                        selected_row = normalized_results[normalized_results["Ticker"] == selected_ticker].iloc[0].to_dict()
                    elif (normalized_news is not None and not normalized_news.empty and selected_ticker in normalized_news["Ticker"].values):
                        nr = normalized_news[normalized_news["Ticker"] == selected_ticker].iloc[0]
                        selected_row = {
                            "Ticker": selected_ticker,
                            "Price": nr.get("Price"), "Entry Range": nr.get("Entry Range"),
                            "Stop Loss": nr.get("Stop Loss"), "Target": nr.get("Target"),
                            "Risk_Reward": nr.get("Risk_Reward"),
                            "High_Conviction": True, "Superstar_Buying": False,
                            "Strategy": f"News: {nr.get('Catalyst', 'News')}",
                            "Institutional_Details": nr.get("Headline"),
                        }
                    elif (normalized_medium is not None and not normalized_medium.empty and selected_ticker in normalized_medium["Ticker"].values):
                        selected_row = normalized_medium[normalized_medium["Ticker"] == selected_ticker].iloc[0].to_dict()

                    if selected_row:
                        dc1, dc2 = st.columns(2)

                        def _trow(lbl, val, vc="#e6edf3"):
                            return (f'<div style="display:flex;justify-content:space-between;'
                                    f'padding:8px 0;border-bottom:1px solid #21262d;">'
                                    f'<span style="font-size:.76rem;color:#6e7f96;">{lbl}</span>'
                                    f'<span style="font-family:JetBrains Mono,monospace;'
                                    f'font-size:.8rem;font-weight:600;color:{vc};">{val}</span></div>')

                        with dc1:
                            badge = ""
                            if selected_row.get("Superstar_Buying"):
                                badge = (f'<div style="background:rgba(247,129,102,.12);color:#f78166;'
                                         f'border:1px solid rgba(247,129,102,.3);border-radius:5px;'
                                         f'padding:4px 10px;font-size:.7rem;font-weight:700;'
                                         f'display:inline-block;margin-bottom:10px;">'
                                         f'🔥 SUPERSTAR: {selected_row.get("Superstar_Names","")}</div>')
                            elif selected_row.get("High_Conviction"):
                                badge = ('<div style="background:rgba(63,185,80,.1);color:#3fb950;'
                                         'border:1px solid rgba(63,185,80,.3);border-radius:5px;'
                                         'padding:4px 10px;font-size:.7rem;font-weight:700;'
                                         'display:inline-block;margin-bottom:10px;">💎 INSTITUTIONAL</div>')

                            st.markdown(f"""
                            <div style="background:#0d1117;border:1px solid #21262d;border-radius:10px;padding:18px 20px;">
                              <div style="font-size:.85rem;font-weight:700;color:#e6edf3;margin-bottom:12px;">🎯 Trade Setup</div>
                              {badge}
                              {_trow("Strategy", selected_row.get("Strategy","—"), "#79c0ff")}
                              {_trow("Live Price", f"₹{ltp:,.2f}", ltp_color)}
                              {_trow("Entry Range", f"₹{selected_row.get('Entry Range','—')}")}
                              {_trow("Stop Loss",   f"₹{selected_row.get('Stop Loss','—')}", "#f85149")}
                              {_trow("Target",      f"₹{selected_row.get('Target','—')}",    "#3fb950")}
                              {_trow("Risk:Reward", selected_row.get("Risk_Reward","—"))}
                              {_trow("RSI (14)",    f"{r['RSI']:.1f}")}
                              {_trow("VWAP",        f"₹{r['VWAP']:,.2f}", vwap_c)}
                              {_trow("Vol Ratio",   f"{r['Vol_Ratio']:.2f}×")}
                            </div>
                            """, unsafe_allow_html=True)

                        with dc2:
                            notes = (
                                selected_row.get("Institutional_Details") or
                                selected_row.get("Reason") or
                                selected_row.get("Headline") or
                                "Technical setup confirmed. No additional institutional details available."
                            )
                            st.markdown(f"""
                            <div style="background:#0d1117;border:1px solid #21262d;border-radius:10px;padding:18px 20px;">
                              <div style="font-size:.85rem;font-weight:700;color:#e6edf3;margin-bottom:12px;">📝 Analysis Notes</div>
                              <div style="font-size:.8rem;color:#8892a4;line-height:1.75;margin-bottom:16px;">{notes}</div>
                              <div style="background:#161b22;border:1px solid #21262d;border-radius:7px;padding:12px 14px;">
                                <div style="font-size:.65rem;color:#6e7f96;font-weight:700;text-transform:uppercase;
                                            letter-spacing:.08em;margin-bottom:7px;">Exit Rules</div>
                                <div style="font-size:.76rem;color:#8892a4;line-height:1.7;">
                                  Exit on <span style="color:#f85149;font-weight:700;">Stop Loss</span> hit or
                                  <span style="color:#3fb950;font-weight:700;">Target</span> hit.<br>
                                  Max hold: <b style="color:#e6edf3;">5 days</b> (short) ·
                                  <b style="color:#e6edf3;">30 days</b> (medium-term).
                                </div>
                              </div>
                            </div>
                            """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    # TAB 4 — 3-Month Multi-Strategy Optimizer
    # ══════════════════════════════════════════════════════════════
    with tab5:
        st.markdown("""
        <div class="infobox">
          <b>3-Month Multi-Strategy Backtester & Optimizer</b><br>
          Run individual strategies and their mixed combinations (AND, OR, Consensus models) 
          over the past 3 months (max 5-day hold). Select <b>Single Stock Analysis</b> to deep-dive, or 
          <b>Universe-Wide Leaderboard Scanner</b> to search all stocks for <b>95%+ Target Hit Rate</b> setups.
        </div>
        """, unsafe_allow_html=True)

        opt_mode = st.radio("Optimizer Mode", ["Single Stock Analysis", "Universe-Wide Leaderboard Scanner"], horizontal=True, key="opt_mode_toggle")

        if opt_mode == "Single Stock Analysis":
            all_syms_opt = list(dict.fromkeys(
                (results_df["Ticker"].tolist() if not results_df.empty else []) +
                (news_df_session["Ticker"].tolist()
                 if news_df_session is not None and not news_df_session.empty else []) +
                (medium_df_session["Ticker"].tolist()
                 if medium_df_session is not None and not medium_df_session.empty else [])
            ))
            
            if not all_syms_opt:
                all_syms_opt = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "SBIN.NS", "INFY.NS"]

            c1, c2 = st.columns(2)
            with c1:
                sel_ticker = st.selectbox(
                    "Select stock from picks",
                    options=all_syms_opt,
                    format_func=lambda x: x.replace(".NS", ""),
                    key="opt_sel_ticker"
                )
                custom_ticker = st.text_input("Or enter any other NSE symbol (e.g. SBIN, TATAMOTORS)", key="opt_custom_ticker").strip().upper()
                
                ticker_to_opt = f"{custom_ticker}.NS" if custom_ticker else sel_ticker
                
            with c2:
                opt_backtest_days = st.slider("Backtest Window (Trading Days ~ 3 months = 60)", min_value=20, max_value=120, value=60, step=5, key="opt_window_days")
                opt_hold_days = st.slider("Max Holding Period (Trading Days)", min_value=1, max_value=20, value=5, step=1, key="opt_hold_days")

            run_opt = st.button("⚡ Run Multi-Strategy Optimization", key="run_opt_trigger")

            if run_opt:
                with st.spinner(f"Running multi-strategy optimization for {ticker_to_opt.replace('.NS', '')}..."):
                    df_hist = None
                    if ticker_to_opt in data_cache:
                        df_hist = data_cache[ticker_to_opt]
                    else:
                        df_hist = dp.get_single_stock_data(ticker_to_opt, period="1y")
                    
                    if df_hist is None or df_hist.empty:
                        st.error(f"Could not retrieve historical EOD data for {ticker_to_opt}. Please ensure the symbol is valid.")
                    else:
                        summary_df, trade_logs = opt.run_3month_optimization(df_hist, hold_days=opt_hold_days, backtest_days=opt_backtest_days, ticker=ticker_to_opt)
                        st.session_state.opt_summary = summary_df
                        st.session_state.opt_logs = trade_logs
                        st.session_state.opt_ticker_run = ticker_to_opt

            if st.session_state.get("opt_summary") is not None and st.session_state.get("opt_ticker_run") is not None:
                opt_sum = st.session_state.opt_summary
                opt_logs = st.session_state.opt_logs
                t_run = st.session_state.opt_ticker_run.replace(".NS", "")
                
                st.markdown(f"### 📊 Strategy Optimization: **{t_run}**")
                
                if opt_sum.empty:
                    st.warning("No trades were triggered for any strategy configuration in this backtest window.")
                else:
                    best_strat = opt_sum.iloc[0]
                    best_rate = best_strat["Target Hit Rate (%)"]
                    has_95 = any(opt_sum["Target Hit Rate (%)"] >= 95.0)
                    
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    with mc1:
                        st.metric("Best Strategy", best_strat["Strategy"])
                    with mc2:
                        st.metric("Target Hit Rate", f"{best_rate:.1f}%", delta="🏆 95% Hit!" if best_rate >= 95.0 else None)
                    with mc3:
                        st.metric("Total Trades", int(best_strat["Total Trades"]))
                    with mc4:
                        st.metric("Avg P&L per Trade", f"{best_strat['Avg P&L (%)']:+.2f}%")
                        
                    if has_95:
                        st.success("🎉 **Success:** Found mixed/individual strategies that hit the **95%+ Target Hit Rate** threshold! (Highlighted in green below)")
                    else:
                        st.warning("⚠️ No strategy configuration achieved the **95% Target Hit Rate** threshold. Showing top performing configurations.")
                    
                    def highlight_95_rows(row):
                        if row["Target Hit Rate (%)"] >= 95.0 and row["Total Trades"] > 0:
                            return ["background-color: rgba(63, 185, 80, 0.18); border-left: 3px solid #3fb950;"] * len(row)
                        return [""] * len(row)
                    
                    try:
                        styled_summary = opt_sum.style.apply(highlight_95_rows, axis=1)
                    except Exception:
                        styled_summary = opt_sum
                        
                    st.dataframe(
                        styled_summary,
                        column_config={
                            "Target Hit Rate (%)": st.column_config.NumberColumn("Hit Rate", format="%.2f%%"),
                            "Avg P&L (%)": st.column_config.NumberColumn("Avg P&L", format="%+.2f%%"),
                            "Total Trades": st.column_config.NumberColumn("Trades"),
                            "Target Hits": st.column_config.NumberColumn("Hits"),
                            "Stop Loss Hits": st.column_config.NumberColumn("SL Hits"),
                            "Time Exits": st.column_config.NumberColumn("Time Exits"),
                        },
                        hide_index=True,
                        width='stretch'
                    )
                    
                    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
                    st.markdown("### 📝 Detailed Trade Logs")
                    selected_strat = st.selectbox(
                        "Select strategy to inspect individual trades",
                        options=opt_sum["Strategy"].tolist(),
                        key="opt_inspect_strat"
                    )
                    
                    if selected_strat:
                        strat_trades = opt_logs.get(selected_strat, [])
                        if not strat_trades:
                            st.info("No trades triggered for this strategy.")
                        else:
                            trades_df = pd.DataFrame(strat_trades)
                            def _highlight_opt_status(row):
                                s, p = row.get("Status", ""), row.get("P&L (%)", 0)
                                if s == "Target Hit":
                                    return f"🟢 Target Hit (+{p:.2f}%)"
                                elif s == "Stop Loss Hit":
                                    return f"🔴 Stop Loss ({p:.2f}%)"
                                else:
                                    return f"🟡 Time Exit ({p:+.2f}%)"
                            
                            trades_df["Outcome"] = trades_df.apply(_highlight_opt_status, axis=1)
                            show_trades = trades_df[["Trigger Date", "Exit Date", "Entry Price", "Target", "Stop Loss", "Exit Price", "Days Held", "Outcome"]].copy()
                            # Coerce numeric columns to prevent PyArrow serialization ArrowTypeError
                            for numeric_col in ["Entry Price", "Target", "Stop Loss", "Exit Price", "Days Held"]:
                                if numeric_col in show_trades.columns:
                                    show_trades[numeric_col] = pd.to_numeric(show_trades[numeric_col], errors='coerce')
                            st.dataframe(
                                show_trades,
                                column_config={
                                    "Entry Price": st.column_config.NumberColumn("Entry Price (₹)", format="₹%.2f"),
                                    "Target": st.column_config.NumberColumn("Target (₹)", format="₹%.2f"),
                                    "Stop Loss": st.column_config.NumberColumn("SL (₹)", format="₹%.2f"),
                                    "Exit Price": st.column_config.NumberColumn("Exit Price (₹)", format="₹%.2f"),
                                    "Days Held": st.column_config.NumberColumn("Hold Days"),
                                },
                                hide_index=True,
                                width='stretch'
                            )

        elif opt_mode == "Universe-Wide Leaderboard Scanner":
            # Scan active universe (data_cache)
            if not data_cache:
                st.warning("No data cache available. Please click 'Run Full Analysis' in the sidebar first.")
            else:
                c1, c2, c3 = st.columns(3)
                with c1:
                    opt_backtest_days = st.slider("Backtest Window (Trading Days ~ 3 months = 60)", min_value=20, max_value=120, value=60, step=5, key="ld_window_days")
                with c2:
                    opt_hold_days = st.slider("Max Holding Period (Trading Days)", min_value=1, max_value=20, value=5, step=1, key="ld_hold_days")
                with c3:
                    min_trades = st.number_input("Minimum Required Trades", min_value=1, max_value=10, value=3, step=1, key="ld_min_trades")

                threshold_rate = st.slider("Highlight Win Rate Threshold (%)", min_value=50.0, max_value=100.0, value=95.0, step=1.0, key="ld_threshold")

                run_scan = st.button("🔍 Scan Active Universe", key="run_ld_trigger")

                if run_scan:
                    leaderboard_records = []
                    # Progress indicators
                    stocks_to_scan = list(data_cache.keys())
                    prog_text = st.empty()
                    prog_bar = st.progress(0.0)
                    
                    # We run in a fast loop
                    import time as pytime
                    start_time = pytime.time()
                    
                    for idx, ticker in enumerate(stocks_to_scan):
                        prog_text.text(f"Scanning {ticker.replace('.NS','')} ({idx+1}/{len(stocks_to_scan)})...")
                        prog_bar.progress((idx+1)/len(stocks_to_scan))
                        
                        df_stock = data_cache[ticker]
                        sum_df, _ = opt.run_3month_optimization(df_stock, hold_days=opt_hold_days, backtest_days=opt_backtest_days, ticker=ticker)
                        
                        if not sum_df.empty:
                            # Filter stocks that meet the min trades criterion
                            filtered_df = sum_df[sum_df["Total Trades"] >= min_trades].copy()
                            if not filtered_df.empty:
                                for _, row in filtered_df.iterrows():
                                    leaderboard_records.append({
                                        "Stock": ticker.replace(".NS", ""),
                                        "Strategy": row["Strategy"],
                                        "Type": row["Type"],
                                        "Total Trades": int(row["Total Trades"]),
                                        "Target Hits": int(row["Target Hits"]),
                                        "Target Hit Rate (%)": row["Target Hit Rate (%)"],
                                        "Avg P&L (%)": row["Avg P&L (%)"]
                                    })
                                    
                    prog_text.empty()
                    prog_bar.empty()
                    
                    scan_dur = pytime.time() - start_time
                    st.toast(f"✅ Scanned {len(stocks_to_scan)} stocks in {scan_dur:.2f} seconds!", icon="⚡")
                    
                    leader_df = pd.DataFrame(leaderboard_records)
                    if not leader_df.empty:
                        # Sort by Target Hit Rate DESC, Total Trades DESC, Avg PnL DESC
                        leader_df = leader_df.sort_values(by=["Target Hit Rate (%)", "Total Trades", "Avg P&L (%)"], ascending=[False, False, False]).reset_index(drop=True)
                    st.session_state.opt_leaderboard = leader_df

                if st.session_state.get("opt_leaderboard") is not None:
                    leader_df = st.session_state.opt_leaderboard
                    
                    st.markdown("### 🏆 Universe-Wide Strategy Leaderboard")
                    
                    ld_display_type = st.radio(
                        "Select Leaderboard Display View",
                        ["Stock-Specific Combinations", "Strategy-Specific Aggregate (Winning Strategies)"],
                        horizontal=True,
                        key="ld_display_type"
                    )
                    
                    if leader_df.empty:
                        st.warning("No strategy configurations matched the criteria across the scanned universe.")
                    else:
                        if ld_display_type == "Strategy-Specific Aggregate (Winning Strategies)":
                            # Aggregate by Strategy and Type
                            agg_df = leader_df.groupby(["Strategy", "Type"]).agg(
                                Total_Trades=("Total Trades", "sum"),
                                Target_Hits=("Target Hits", "sum"),
                                Avg_PnL=("Avg P&L (%)", "mean"),
                                Stocks_Traded=("Stock", "count")
                            ).reset_index()
                            
                            agg_df["Target Hit Rate (%)"] = (agg_df["Target_Hits"] / agg_df["Total_Trades"]) * 100
                            agg_df["Target Hit Rate (%)"] = agg_df["Target Hit Rate (%)"].fillna(0.0).round(2)
                            agg_df["Avg P&L (%)"] = agg_df["Avg_PnL"].round(2)
                            
                            leader_df_to_show = agg_df.rename(columns={
                                "Total_Trades": "Total Trades",
                                "Target_Hits": "Target Hits",
                                "Stocks_Traded": "Stocks Traded"
                            })[["Strategy", "Type", "Stocks Traded", "Total Trades", "Target Hits", "Target Hit Rate (%)", "Avg P&L (%)"]]
                            
                            # Sort by Hit Rate DESC, Total Trades DESC
                            leader_df_to_show = leader_df_to_show.sort_values(by=["Target Hit Rate (%)", "Total Trades"], ascending=[False, False]).reset_index(drop=True)
                            badge_name = "Winning Strategies"
                        else:
                            leader_df_to_show = leader_df.copy()
                            badge_name = "Stock-Strategy Combinations"
                            
                        # Filter or show highlights
                        has_threshold = any(leader_df_to_show["Target Hit Rate (%)"] >= threshold_rate)
                        matching_count = len(leader_df_to_show[leader_df_to_show["Target Hit Rate (%)"] >= threshold_rate])
                        
                        if has_threshold:
                            st.success(f"🎉 **Success:** Found **{matching_count}** {badge_name} that achieved **{threshold_rate:.1f}%+ target hit rate**! (Highlighted in green)")
                        else:
                            st.info(f"ℹ️ No setups reached the {threshold_rate:.1f}% target hit rate. Showing top performers.")

                        # Table styler
                        def highlight_ld_rows(row):
                            if row["Target Hit Rate (%)"] >= threshold_rate:
                                return ["background-color: rgba(63, 185, 80, 0.18); border-left: 3px solid #3fb950;"] * len(row)
                            return [""] * len(row)
                            
                        try:
                            styled_ld = leader_df_to_show.style.apply(highlight_ld_rows, axis=1)
                        except Exception:
                            styled_ld = leader_df_to_show
                            
                        st.dataframe(
                            styled_ld,
                            column_config={
                                "Target Hit Rate (%)": st.column_config.NumberColumn("Hit Rate", format="%.2f%%"),
                                "Avg P&L (%)": st.column_config.NumberColumn("Avg P&L", format="%+.2f%%"),
                                "Total Trades": st.column_config.NumberColumn("Total Trades"),
                                "Target Hits": st.column_config.NumberColumn("Hits"),
                                "Stocks Traded": st.column_config.NumberColumn("Stocks Count"),
                            },
                            hide_index=True,
                            width='stretch'
                        )
                        
                        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
                        st.download_button(
                            "📥 Export Leaderboard (CSV)",
                            data=leader_df_to_show.to_csv(index=False).encode(),
                            file_name=f"strategy_leaderboard_{datetime.date.today()}.csv",
                            mime="text/csv",
                            key="download_leaderboard_csv"
                        )

    # ══════════════════════════════════════════════════════════════
    # TAB 7 — Analysis History with validation + Broker stats
    # ══════════════════════════════════════════════════════════════
    with tab6:
        st.markdown("""
        <div class="infobox">
          <b>📜 Persistent Analysis History with Target/SL Validation</b><br>
          Every full analysis run is saved. Previous picks are automatically validated against 
          current prices: <b style="color:#3fb950;">Target Met ✅</b> / 
          <b style="color:#f85149;">Stop Loss Hit 🔴</b> / 
          <b style="color:#a78bfa;">Active 🟡</b> / Expired.
          Short trades (SELL-BUY) are validated with reversed SL/Target logic.
        </div>
        """, unsafe_allow_html=True)

        history_cache = hist.load_history_cache()
        
        # ── Overall Stats ──
        stats = hist.get_history_stats(history_cache)
        if stats["total_picks"] > 0:
            hc1, hc2, hc3, hc4, hc5 = st.columns(5)
            hc1.metric("Total Historical Picks", stats["total_picks"])
            hc2.metric("✅ Target Met", stats["target_met"])
            hc3.metric("🔴 Stop Loss Hit", stats["stop_loss_hit"])
            hc4.metric("🟡 Active", stats["active"])
            hc5.metric("🏆 Win Rate", f"{stats['win_rate']:.1f}%")
            
            st.markdown(f'<div style="margin-top:-8px; margin-bottom:12px; color:#5a7a9a; font-size:0.75rem;">Avg P&L: {stats["avg_pnl"]:+.2f}% · Expired: {stats["expired"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="infobox">No analysis history yet. Run a full analysis to start tracking.</div>', unsafe_allow_html=True)

        # ── History Data Table ──
        hist_df = hist.get_history_as_dataframe(history_cache)
        if not hist_df.empty:
            _sec_header("📋", "All Historical Picks (Last 60 Days)", count=len(hist_df))
            
            # Filter controls
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                status_filter = st.multiselect(
                    "Filter by Status",
                    options=["Active", "Target Met", "Stop Loss Hit", "Expired"],
                    default=[],
                    key="hist_status_filter"
                )
            with col_f2:
                source_filter = st.multiselect(
                    "Filter by Source",
                    options=["swing", "medium", "intraday", "news"],
                    default=[],
                    key="hist_source_filter"
                )
            
            display_df = hist_df.copy()
            if status_filter:
                display_df = display_df[display_df["Status"].isin(status_filter)]
            if source_filter:
                display_df = display_df[display_df["Source"].isin(source_filter)]
            
            if not display_df.empty:
                # Sort by Entry Date descending
                display_df = display_df.sort_values("Entry Date", ascending=False)
                
                # Color code the Status column
                def _style_status(val):
                    if val == "Target Met":
                        return "color: #3fb950; font-weight: 700;"
                    elif val == "Stop Loss Hit":
                        return "color: #f85149; font-weight: 700;"
                    elif val == "Active":
                        return "color: #a78bfa; font-weight: 700;"
                    return ""
                
                try:
                    styled_hist = display_df.style.map(_style_status, subset=["Status"])
                except Exception:
                    styled_hist = display_df
                
                st.dataframe(
                    styled_hist,
                    column_config={
                        "Entry Date": st.column_config.TextColumn("Date"),
                        "Ticker": st.column_config.TextColumn("Stock"),
                        "Strategy": st.column_config.TextColumn("Strategy"),
                        "Type": st.column_config.TextColumn("Type"),
                        "Source": st.column_config.TextColumn("Source"),
                        "Price": st.column_config.NumberColumn("Price (₹)", format="₹%.2f"),
                        "Target": st.column_config.NumberColumn("Target (₹)", format="₹%.2f"),
                        "Stop Loss": st.column_config.NumberColumn("SL (₹)", format="₹%.2f"),
                        "Status": st.column_config.TextColumn("Status"),
                        "P&L (%)": st.column_config.NumberColumn("P&L", format="%+.2f%%"),
                        "Exit Price": st.column_config.NumberColumn("Exit (₹)", format="₹%.2f"),
                        "Exit Date": st.column_config.TextColumn("Exit Date"),
                    },
                    hide_index=True,
                    width='stretch',
                    height=400,
                )
                
                st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
                st.download_button(
                    "📥 Export History (CSV)",
                    data=display_df.to_csv(index=False).encode(),
                    file_name=f"analysis_history_{datetime.date.today()}.csv",
                    mime="text/csv",
                    key="download_history_csv"
                )
            else:
                st.markdown('<div class="infobox">No entries match the selected filters.</div>', unsafe_allow_html=True)
        
        # ── Broker Stats Section ──
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        _sec_header("🏦", "Broker Call Success Rate", badge="Per-Broker Win Rate")
        
        broker_stats_df = hist.get_broker_stats_dataframe(history_cache)
        if not broker_stats_df.empty:
            st.dataframe(
                broker_stats_df,
                column_config={
                    "Broker": st.column_config.TextColumn("Broker"),
                    "Total Calls": st.column_config.NumberColumn("Total Calls"),
                    "Successful": st.column_config.NumberColumn("Successful"),
                    "Win Rate (%)": st.column_config.NumberColumn("Win Rate", format="%.1f%%"),
                },
                hide_index=True,
                width='stretch',
            )
        else:
            st.markdown('<div class="infobox">No broker call history yet. Broker picks with ticker & target will be tracked automatically on each full analysis run.</div>', unsafe_allow_html=True)

        # ── Recent Broker Calls ──
        if history_cache.get("broker_history"):
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
            _sec_header("📋", "Recent Broker Calls", count=len(history_cache["broker_history"]))
            broker_df = pd.DataFrame(history_cache["broker_history"])
            if not broker_df.empty:
                broker_df = broker_df.sort_values("Entry Date", ascending=False).head(20)
                st.dataframe(
                    broker_df,
                    column_config={
                        "Broker": st.column_config.TextColumn("Broker"),
                        "Ticker": st.column_config.TextColumn("Stock"),
                        "Action": st.column_config.TextColumn("Action"),
                        "Target": st.column_config.NumberColumn("Target (₹)", format="₹%.2f"),
                        "Current Price": st.column_config.NumberColumn("Current (₹)", format="₹%.2f"),
                        "Status": st.column_config.TextColumn("Status"),
                        "Entry Date": st.column_config.TextColumn("Date"),
                    },
                    hide_index=True,
                    width='stretch',
                )

# ─────────────────────────────────────────────────────────────────────────────
# EMPTY STATE (before first run)
# ─────────────────────────────────────────────────────────────────────────────
else:
    st.markdown("""
    <div style="padding:4px 0 14px; margin-top:-10px;">
      <h2 style="margin:0; font-size:1.15rem; font-weight:800; color:#dde5f0; letter-spacing:-0.01em;">
        📰  PULSE NEWS DESK & MARKET INTELLIGENCE CENTER
      </h2>
      <p style="font-size:0.75rem; color:#5a7a9a; margin-top:2px; margin-bottom:12px;">
        Real-time news catalysts parsed from active financial feeds. Initialized automatically on startup.
      </p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 2])
    
    # Filter news into Market (Macro) and Stock (Micro) scopes
    if st.session_state.news_picks is not None and not st.session_state.news_picks.empty:
        market_news = st.session_state.news_picks[st.session_state.news_picks["Scope"] == "Market"]
        stock_news = st.session_state.news_picks[st.session_state.news_picks["Scope"] == "Stock"]
    else:
        market_news = pd.DataFrame()
        stock_news = pd.DataFrame()
        
    with col1:
        _sec_header("🌎", "Global Market Sentiment & Macro Highlights", count=len(market_news) if not market_news.empty else 0)
        if market_news.empty:
            st.markdown('<div class="infobox">No major macro-level market updates found in today\'s news feeds.</div>', unsafe_allow_html=True)
        else:
            for _, row in market_news.iterrows():
                headline = row.get("Headline", "")
                sentiment = row.get("Sentiment", "Positive")
                catalyst = row.get("Catalyst", "Macro Catalyst")
                dt_str = row.get("DateTime", "")
                if "T" in dt_str:
                    dt_str = dt_str.split("T")[0]
                
                badge_color = "#00c853" if sentiment == "Positive" else "#ff4d4d"
                bg_color = "rgba(0, 200, 83, 0.04)" if sentiment == "Positive" else "rgba(255, 77, 77, 0.04)"
                border_color = "rgba(0, 200, 83, 0.15)" if sentiment == "Positive" else "rgba(255, 77, 77, 0.15)"
                
                st.markdown(f"""
                <div style="background:{bg_color}; border:1px solid {border_color}; border-radius:6px; padding:10px 14px; margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span style="font-size:0.6rem; font-family:'JetBrains Mono',monospace; color:#5a7a9a; font-weight:700; text-transform:uppercase;">{catalyst}</span>
                        <span style="font-size:0.58rem; color:#5a7a9a;">{dt_str}</span>
                    </div>
                    <div style="font-size:0.83rem; font-weight:600; color:#dde5f0; line-height:1.45;">
                        {headline}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
    with col2:
        _sec_header("💼", "Stock-Specific Catalyst Trade Setups", count=len(stock_news) if not stock_news.empty else 0, badge="Actionable Swings")
        if stock_news.empty:
            st.markdown('<div class="infobox">No stock-specific catalyst trade recommendations found. Run Full Analysis to screen technical universes.</div>', unsafe_allow_html=True)
        else:
            _render_cards(stock_news, st.session_state.ltp_cache or {}, card_type="news")
            
    st.markdown("---")
    
    st.markdown("""
    <div class="empty-state" style="padding:32px 24px 36px; margin-top:10px; background: linear-gradient(145deg, #070e1a, #040a12); border: 1px solid #0d1f35; border-radius: 10px;">
      <div class="empty-state-icon" style="font-size: 2.2rem; margin-bottom: 8px;">⚡</div>
      <div class="empty-state-title" style="font-size: 1.1rem; color: #dde5f0; font-weight: 800;">Ready to run a deep market scan?</div>
      <div class="empty-state-sub" style="font-size: 0.78rem; max-width: 540px; margin: 6px auto 20px; color: #5a7a9a; line-height: 1.7;">
        Select your target universe (Nifty 50, 100, 500, 1000 or F&O Stocks) and strategy in the sidebar, 
        then click <b>Run Full Analysis</b>. The engine will screen stocks progressively in batches of 10 and display active opportunities instantly!
      </div>
      <div class="caps-grid">
        <div class="cap-card" style="min-width: 140px; padding: 10px 14px;">
          <div class="cap-lbl">Data Source</div>
          <div class="cap-val" style="font-size: 0.8rem; color: #dde5f0;">NSE · yfinance</div>
        </div>
        <div class="cap-card" style="min-width: 140px; padding: 10px 14px;">
          <div class="cap-lbl">Live Prices</div>
          <div class="cap-val" style="color: #00c853; font-size: 0.8rem;">● nsepython LTP</div>
        </div>
        <div class="cap-card" style="min-width: 140px; padding: 10px 14px;">
          <div class="cap-lbl">Progressive Scan</div>
          <div class="cap-val" style="color: #0080ff; font-size: 0.8rem;">10-by-10 Streaming</div>
        </div>
        <div class="cap-card" style="min-width: 140px; padding: 10px 14px;">
          <div class="cap-lbl">Intraday Mode</div>
          <div class="cap-val" style="color: #fb923c; font-size: 0.8rem;">VWAP & Momentum</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# AUTO-REFRESH TRIGGER (Javascript) — uses setInterval for reliable repeats
# ─────────────────────────────────────────────────────────────────────────────
if auto_refresh and st.session_state.screener_results is not None:
    # Hidden button that triggers Streamlit rerun when clicked
    st.button("hidden_rerun", key="hidden_rerun_btn", help="Internal: auto-refresh trigger")

    # CSS to visually hide the button in all Streamlit layout variants
    st.markdown("""
    <style>
    div.element-container:has(button[aria-label*="hidden_rerun"]),
    div.stButton:has(button[aria-label*="hidden_rerun"]),
    div.element-container:has(button[data-testid*="hidden_rerun"]),
    div.element-container:has(button[key="hidden_rerun_btn"]) {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        overflow: hidden !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # JS uses setInterval (repeating) not setTimeout (one-shot)
    refresh_interval = 2000 if st.session_state.get("is_analyzing") else 60000
    st.html(
        f"""
        <script>
        (function() {{
            const parentDoc = window.parent.document;
            function clickHiddenRerun() {{
                const buttons = parentDoc.querySelectorAll('button');
                for (const btn of buttons) {{
                    const text = (btn.textContent || btn.innerText || '').trim();
                    if (text === 'hidden_rerun' || text.includes('hidden_rerun')) {{
                        let parent = btn.closest('[data-testid="stElementContainer"]')
                                  || btn.closest('.element-container')
                                  || btn.parentElement;
                        if (parent) parent.style.cssText = 'display:none!important;height:0!important;overflow:hidden!important;';
                        btn.click();
                        return;
                    }}
                }}
            }}
            setTimeout(function() {{
                clickHiddenRerun();
                setInterval(clickHiddenRerun, {refresh_interval});
            }}, {refresh_interval});
        }})();
        </script>
        """,
        unsafe_allow_javascript=True,
    )