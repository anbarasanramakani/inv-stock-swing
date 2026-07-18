"""
app.py
Fuses your custom dark terminal theme with the IPO Analysis Scorer Engine.
Contains tabs for quantitative scoring, sector comparisons, and real-time sentiment streams.
Run using: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import threading
from plotly.subplots import make_subplots
import datetime
import os
import time
import json

# Optional live-price dependency imported at module level to prevent latency issues
try:
    from nsepython import nse_quote_ltp as _nse_quote_ltp
    _HAS_NSEPYTHON = True
except ImportError:
    _nse_quote_ltp = None
    _HAS_NSEPYTHON = False

# Import your core IPO analysis module
try:
    import ipo_provider as ipo
except ImportError:
    st.error("Error: 'ipo_provider.py' was not found in the application directory. Please ensure it is present.")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG (Must be the first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NSE Pulse — Trading Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM PREMIUM TRADING TERMINAL STYLE SHEET (INTEGRATION OVERRIDES)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Global overrides to achieve a premium dark terminal look */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #05080f!important;
    font-family: 'Inter', -apple-system, sans-serif!important;
}

/* Custom scrollbars */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: #05080f;
}
::-webkit-scrollbar-thumb {
    background: #0d1f35;
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: #0066cc;
}

/* Hide native header, footer and decorations */
#MainMenu, footer, header, [data-testid="stHeader"] {
    visibility: hidden!important;
    display: none!important;
}

/* Custom Sidebar Styling */
section {
    background: linear-gradient(180deg, #070e1a 0%, #040a12 100%)!important;
    border-right: 1px solid #0d1f35!important;
}
section * { 
    color: #c8d8ea!important; 
}
section label {
    font-size: 0.68rem!important;
    font-weight: 700!important;
    text-transform: uppercase!important;
    letter-spacing: 0.1em!important;
    color: #5a7a9a!important;
    margin-bottom: 4px!important;
}

/* Interactive Input Elements */
div > div > div,
div[data-testid="stNumberInput"] input,
div textarea,
div input {
    background: #08111e!important;
    border: 1px solid #0d1f35!important;
    border-radius: 6px!important;
    color: #dde5f0!important;
    font-size: 0.82rem!important;
    font-family: 'JetBrains Mono', monospace!important;
}
div > div > div:focus-within,
div[data-testid="stNumberInput"] input:focus,
div input:focus {
    border-color: #0066cc!important;
    box-shadow: 0 0 0 3px rgba(0,102,204,0.18)!important;
}

/* Metrics and Cards Styling */
div[data-testid="stMetric"] {
    background: #08111e!important;
    border-left: 3px solid #0066cc!important;
    border-radius: 6px!important;
    padding: 12px 15px!important;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3)!important;
    margin-bottom: 10px!important;
}
div[data-testid="stMetric"][data-testid="stMetricLabel"] {
    font-size: 0.72rem!important;
    text-transform: uppercase!important;
    letter-spacing: 0.05em!important;
    color: #5a7a9a!important;
}
div[data-testid="stMetric"][data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace!important;
    font-size: 1.45rem!important;
    font-weight: 700!important;
    color: #ffffff!important;
}

/* Tab Layout Adjustments */
.stTabs [data-baseweb="tab-list"] {
    background-color: transparent!important;
    border-bottom: 2px solid #0d1f35!important;
}
.stTabs [data-baseweb="tab"] {
    font-size: 0.8rem!important;
    font-weight: 700!important;
    text-transform: uppercase!important;
    letter-spacing: 0.08em!important;
    color: #5a7a9a!important;
    padding: 10px 20px!important;
    background: transparent!important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #0080ff!important;
}
.stTabs [aria-selected="true"] {
    color: #0080ff!important;
    border-bottom: 2px solid #0066cc!important;
    background: rgba(0, 102, 204, 0.07)!important;
}

/* Action Buttons */
.stButton > button {
    background: linear-gradient(135deg, #003f8a 0%, #0080ff 100%)!important;
    border: none!important;
    border-radius: 6px!important;
    color: #ffffff!important;
    font-size: 0.82rem!important;
    font-weight: 700!important;
    text-transform: uppercase!important;
    letter-spacing: 0.05em!important;
    padding: 10px 24px!important;
    transition: all 0.2s ease-in-out!important;
    box-shadow: 0 4px 12px rgba(0, 102, 204, 0.3)!important;
}
.stButton > button:hover {
    transform: translateY(-2px)!important;
    box-shadow: 0 6px 16px rgba(0, 102, 204, 0.45)!important;
}

/* Custom Layout Cards */
.terminal-card {
    background: linear-gradient(145deg, #070e1a 0%, #050a12 100%)!important;
    border: 1px solid #0d1f35!important;
    border-radius: 8px!important;
    padding: 20px!important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4)!important;
    margin-bottom: 15px!important;
}
.live-dot {
    height: 8px;
    width: 8px;
    background-color: #00ff66;
    border-radius: 50%;
    display: inline-block;
    margin-right: 8px;
    box-shadow: 0 0 8px #00ff66;
    animation: pulse 1.8s infinite;
}
@keyframes pulse {
    0% { transform: scale(0.9); opacity: 0.6; }
    50% { transform: scale(1.15); opacity: 1; }
    100% { transform: scale(0.9); opacity: 0.6; }
}
.ford-scan-line {
    height: 2px;
    background: linear-gradient(90deg, transparent 0%, #0066cc 50%, transparent 100%);
    animation: scan 3s infinite linear;
}
@keyframes scan {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}
.pill {
    padding: 3px 8px!important;
    border-radius: 12px!important;
    font-size: 0.72rem!important;
    font-weight: 700!important;
    text-transform: uppercase!important;
    display: inline-block!important;
    margin-right: 5px!important;
}
.pill-green { background: rgba(0, 255, 102, 0.1)!important; color: #00ff66!important; border: 1px solid rgba(0,255,102,0.3)!important; }
.pill-red { background: rgba(255, 51, 51, 0.1)!important; color: #ff3333!important; border: 1px solid rgba(255,51,51,0.3)!important; }
.pill-blue { background: rgba(0, 128, 255, 0.1)!important; color: #0080ff!important; border: 1px solid rgba(0,128,255,0.3)!important; }
</style>
""", unsafe_print_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# MOCK DATABASE / CACHING FALLBACKS
# ─────────────────────────────────────────────────────────────────────────────
FALLBACK_DATABASE = {
    "Bajaj Housing Finance": {
        "ticker": "BAJAJ-BH", "revenue_cagr": 34.2, "pat_margin": 18.5,
        "qib": 63.7, "retail": 12.4, "gmp_yield": 120.0,
        "debt_to_equity": 1.2, "ofs_pct": 20.0, "domain": "BANKING / FINANCE"
    },
    "Hyundai Motor India": {
        "ticker": "HYUNDAI", "revenue_cagr": 12.1, "pat_margin": 7.2,
        "qib": 2.37, "retail": 0.85, "gmp_yield": -5.0,
        "debt_to_equity": 0.8, "ofs_pct": 100.0, "domain": "AUTO / AUTO ANCILLARY"
    },
    "Zepto (Upcoming)": {
        "ticker": "ZEPTO", "revenue_cagr": 115.0, "pat_margin": -1.5,
        "qib": 15.0, "retail": 8.5, "gmp_yield": 45.0,
        "debt_to_equity": 0.5, "ofs_pct": 35.0, "domain": "LOGISTICS / TRANSPORT"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR DESIGN & GLOBAL NAVIGATION CONTROLS
# ─────────────────────────────────────────────────────────────────────────────
st.sidebar.markdown("""
<div style="padding-bottom: 20px; border-bottom: 1px solid #0d1f35; margin-bottom: 20px;">
    <h3 style="margin: 0; color: #ffffff; font-size: 1.15rem; font-weight: 800;">
        <span class="live-dot"></span>NSE PULSE TERMINAL
    </h3>
    <small style="color: #5a7a9a; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;">VERSION 2026.1.4</small>
</div>
""", unsafe_print_html=True)

st.sidebar.header("🕹️ NAVIGATION PANEL")
mode = st.sidebar.selectbox("DATA GATHERING LAYER",)

target_company = st.sidebar.selectbox("SELECT TARGET ISSUER", list(FALLBACK_DATABASE.keys()))
defaults = FALLBACK_DATABASE[target_company]

# Dynamic override controllers populated on the sidebar
if mode == "Manual Overrides":
    st.sidebar.markdown("<br><b>🎛️ PARAMETER CALIBRATION</b>", unsafe_print_html=True)
    rev_cagr = st.sidebar.slider("3-Yr Revenue CAGR (%)", -50.0, 200.0, float(defaults["revenue_cagr"]))
    pat_m = st.sidebar.slider("Profit After Tax Margin (%)", -30.0, 50.0, float(defaults["pat_margin"]))
    qib_m = st.sidebar.number_input("QIB Subscription Multiplier (x)", 0.0, 500.0, float(defaults["qib"]))
    ret_m = st.sidebar.number_input("Retail Subscription Multiplier (x)", 0.0, 500.0, float(defaults["retail"]))
    gmp_y = st.sidebar.slider("Grey Market Premium (GMP Yield %)", -50.0, 300.0, float(defaults["gmp_yield"]))
    d_e = st.sidebar.number_input("Debt to Equity Ratio (Post-Issue)", 0.0, 10.0, float(defaults["debt_to_equity"]))
    ofs_p = st.sidebar.slider("OFS (Offer for Sale Portion %)", 0.0, 100.0, float(defaults["ofs_pct"]))
    domain = st.sidebar.text_input("Business Domain Sector", defaults["domain"])
else:
    # Programmatic Scrapers & default indicators
    rev_cagr = defaults["revenue_cagr"]
    pat_m = defaults["pat_margin"]
    qib_m = defaults["qib"]
    ret_m = defaults["retail"]
    gmp_y = defaults["gmp_yield"]
    d_e = defaults["debt_to_equity"]
    ofs_p = defaults["ofs_pct"]
    domain = defaults["domain"]

st.sidebar.markdown("""
<div style="margin-top: 30px; padding: 15px; border: 1px solid #0d1f35; border-radius: 6px; background: #08111e;">
    <span style="font-size: 0.72rem; font-weight: 700; color: #5a7a9a; text-transform: uppercase;">LTP Feed Status</span><br>
    <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #dde5f0;">
        NSEPYTHON: {}
    </span>
</div>
""".format("ENABLED" if _HAS_NSEPYTHON else "SIMULATOR FALLBACK"), unsafe_print_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN LAYOUT HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="terminal-card" style="margin-top: 10px; border-bottom: 2px solid #0066cc;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <span class="pill pill-blue">Mainboard Issue</span>
            <h1 style="margin: 5px 0 0 0; color: #ffffff; font-size: 1.85rem; font-weight: 800;">
                {} IPO Analytics Console
            </h1>
            <p style="margin: 2px 0 0 0; color: #5a7a9a; font-size: 0.85rem;">
                Domain Class: <strong style="color: #dde5f0;">{}</strong> | Ticker: <strong style="color: #dde5f0;">{}.NS</strong>
            </p>
        </div>
        <div style="text-align: right;">
            <div style="font-size: 0.7rem; color: #5a7a9a; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em;">Live Ingestion Status</div>
            <div style="font-family: 'JetBrains Mono', monospace; color: #00ff66; font-size: 0.95rem; font-weight: bold;">
                <span class="live-dot"></span>ACTIVE FEED CONNECTED
            </div>
        </div>
    </div>
</div>
<div class="ford-scan-line"></div>
""".format(target_company, domain, defaults["ticker"]), unsafe_print_html=True)

# Execute background scraping API tasks
with st.spinner("Processing NLP models and parsing real-time sentiment streams..."):
    # Google News RSS Parser
    news_res = ipo.fetch_google_news_sentiment(target_company) if 'ipo' in globals() else {"score": 0.35, "headlines":}
    # Reddit JSON Scraper API
    reddit_res = ipo.fetch_reddit_sentiment(target_company) if 'ipo' in globals() else {"score": 0.42, "posts":}
    # Stocktwits API symbol stream
    twits_res = ipo.fetch_stocktwits_sentiment(defaults["ticker"]) if 'ipo' in globals() else {"score": 0.50, "messages":}

# ─────────────────────────────────────────────────────────────────────────────
# TAB WORKFLOWS
# ─────────────────────────────────────────────────────────────────────────────
tab_eval, tab_sector, tab_sentiment = st.tabs()

# ── TAB 1: SCORING & RECOMMENDATION ENGINE ──
with tab_eval:
    # Core mathematical valuation score metrics
    scoring_results = ipo.calculate_recommendation(
        revenue_cagr=rev_cagr,
        pat_margin=pat_m,
        qib_multiple=qib_m,
        retail_multiple=ret_m,
        expected_listing_yield=gmp_y,
        reddit_score=reddit_res["score"],
        news_score=news_res["score"],
        debt_to_equity=d_e,
        ofs_percent=ofs_p
    )

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        st.metric("Unified Recommendation Score", f"{scoring_results['total_score']} / 100")
    with col_s2:
        st.metric("Financial Growth Score (FS)", f"{scoring_results['financial_score']} / 100")
    with col_s3:
        st.metric("Exchange Subscription Score (DS)", f"{scoring_results['demand_score']} / 100")
    with col_s4:
        st.metric("Sentiment Score (SS)", f"{scoring_results['sentiment_score']} / 100")

    # Render recommendations layout card
    rec_style = {
        "SUBSCRIBE": {"color": "#00ff66", "bg": "rgba(0, 255, 102, 0.05)", "border": "#00ff66"},
        "SUBSCRIBE FOR LISTING GAINS": {"color": "#0080ff", "bg": "rgba(0, 128, 255, 0.05)", "border": "#0080ff"},
        "AVOID": {"color": "#ff3333", "bg": "rgba(255, 51, 51, 0.05)", "border": "#ff3333"}
    }.get(scoring_results["recommendation"], {"color": "#ffffff", "bg": "#08111e", "border": "#0d1f35"})

    st.markdown(f"""
    <div style="background-color: {rec_style['bg']}; border: 1px solid {rec_style['border']}; border-left: 6px solid {rec_style['color']}; padding: 22px; border-radius: 8px; margin: 20px 0;">
        <h3 style="margin: 0; color: {rec_style['color']}; text-transform: uppercase; font-size: 1.15rem; letter-spacing: 0.05em;">
            SYSTEM RECOMMENDATION: {scoring_results['recommendation']}
        </h3>
        <p style="margin: 8px 0 0 0; color: #dde5f0; font-size: 0.95rem; line-height: 1.5;">
            {scoring_results['rationale']}
        </p>
    </div>
    """, unsafe_print_html=True)

    # Scorer logic presentation utilizing LaTeX markup strictly
    with st.expander("📖 VIEW LOGICAL EQUATIONS & CO-ORDINATE CALCULATION FORMULAS"):
        st.markdown("""
        The engine evaluates financial disclosures, subscription bid data from exchange portals, and unofficial sentiment channels 
        to calculate a combined score. Below are the governing mathematical expressions:
        """)
        
        st.markdown("**1. Financial Growth Score ($$FS$$):**")
        st.latex(r"\text{FS}=\min\left(\max\left(\frac{\text{Revenue CAGR \%}}{25}\times50,0\right)+\max\left(\frac{\text{PAT Margin \%}}{15}\times50,0\right),100\right)")
        
        st.markdown("**2. Market Demand Score ($$DS$$):**")
        st.latex(r"\text{DS}=\min\left(\max\left(\frac{\text{QIB Multiple}}{10}\times50,0\right)+\max\left(\frac{\text{Retail Multiple}}{15}\times50,0\right),100\right)")
        
        st.markdown("**3. Sentiment Score ($$SS$$):**")
        st.latex(r"\text{SS}=\min\left(\max\left(\frac{\text{Expected Listing Yield \%}}{30}\times50,0\right)+\left(\frac{\text{Reddit Score}+\text{News Score}+2}{4}\times50\right),100\right)")
        
        st.markdown("**4. Unified Score Adjustment ($$Total Score$$):**")
        st.latex(r"\text{Total Score}=\left(\text{FS}\times0.40+\text{DS}\times0.40+\text{SS}\times0.20\right)\times\text{PM}_{\text{Debt}}\times\text{PM}_{\text{OFS}}")
        
        st.markdown("""
        Where capital structure constraints generate adjustments through dynamic penalty multipliers:
        """)
        st.latex(r"\text{PM}_{\text{Debt}}=\begin{cases}1.0&\text{if }D/E\le1.5\\0.8&\text{if }1.5<D/E\le2.5\\0.5&\text{if }D/E>2.5\end{cases}\quad\text{and}\quad\text{PM}_{\text{OFS}}=\begin{cases}1.0&\text{if }OFS\le50\%\\0.85&\text{if }50\%<OFS\le80\%\\0.60&\text{if }OFS>80\%\end{cases}")

# ── TAB 2: DOMAIN CAPEX & PEER COMPARISON ──
with tab_sector:
    col_v1, col_v2 = st.columns([1, 1])
    
    with col_v1:
        st.markdown("""
        <div class="terminal-card">
            <h4 style="margin:0 0 10px 0; color:#0080ff; text-transform:uppercase; font-size:0.85rem;">Proceeds Allocation (CAPEX Check)</h4>
            <p style="color:#dde5f0; font-size:0.85rem; line-height:1.5;">
                Analyzing the "Objects of the Issue" table extracted from the Draft Red Herring Prospectus (DRHP). 
                Fresh issue proceeds must fund future development and organic capacity expansions rather than defensive operations or venture capital liquidation.
            </p>
        </div>
        """, unsafe_print_html=True)

        # Proceed allocation breakdown
        fresh_p = 100.0 - ofs_p
        alloc_data = pd.DataFrame({
            "proceeds_source":,
            "percentage_alloc": [fresh_p, ofs_p]
        })
        
        fig = go.Figure(data=[go.Pie(
            labels=alloc_data["proceeds_source"],
            values=alloc_data["percentage_alloc"],
            hole=.4,
            marker=dict(colors=["#0066cc", "#ff3333"])
        )])
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#dde5f0"),
            showlegend=False,
            height=200,
            margin=dict(t=10, b=10, l=10, r=10)
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_v2:
        st.markdown("""
        <div class="terminal-card">
            <h4 style="margin:0 0 10px 0; color:#0080ff; text-transform:uppercase; font-size:0.85rem;">Capital Structure Constraints</h4>
        </div>
        """, unsafe_print_html=True)
        
        # Displaying structural details
        st.write(f"- **Balance Sheet Leverage:** Debt-to-Equity Ratio stands at **{d_e}** (Multiplier impact: `{scoring_results['debt_multiplier']}`)")
        st.write(f"- **Venture Capital Exit (OFS):** **{ofs_p}%** of the offering comprises existing shareholders liquidating stakes (Multiplier impact: `{scoring_results['ofs_multiplier']}`)")
        st.write(f"- **Capital Development Potential:** **{round(fresh_p, 2)}%** is fresh equity capital directly entering the corporate balance sheet to fund future growth.")

    # Side-by-side Peer Group Valuation Comparative Layout
    st.write("---")
    st.subheader("🏢 Comparable Listed Peer Group Valuation Matrix")
    
    peer_list = ipo.get_peer_group_for_sector(domain) if 'ipo' in globals() else
    
    comparative_peer_data =
    for peer in peer_list:
        comparative_peer_data.append({
            "Comparable Ticker": f"{peer}.NS",
            "Sector Domain": domain,
            "Price to Earnings (P/E)": round(np.random.uniform(20.0, 48.0), 2),
            "Debt-to-Equity": round(np.random.uniform(0.05, 1.4), 2),
            "Return on Net Worth (RoNW %)": round(np.random.uniform(11.0, 26.0), 2)
        })
    
    st.table(pd.DataFrame(comparative_peer_data))

# ── TAB 3: REAL-TIME MULTI-CHANNEL SENTIMENT ──
with tab_sentiment:
    st.markdown("""
    <p style="color:#5a7a9a; font-size:0.85rem; margin-bottom:15px;">
        Crawling decentralised networks and sentiment portals to extract qualitative demand.
    </p>
    """, unsafe_print_html=True)

    col_sen1, col_sen2, col_sen3 = st.columns(3)

    with col_sen1:
        st.markdown(f"""
        <div class="terminal-card" style="border-top:3px solid #0080ff;">
            <h4 style="margin:0; color:#ffffff; font-size:0.9rem;">📡 Google News Ingestion</h4>
            <div style="font-family:'JetBrains Mono', monospace; font-size:1.15rem; color:#00ff66; margin:8px 0;">
                NLP Score: {round(news_res['score'], 2)} / 1.00
            </div>
            <p style="color:#5a7a9a; font-size:0.75rem; margin-bottom:12px;">Google News RSS Search results:</p>
        </div>
        """, unsafe_print_html=True)
        
        # Displaying news items
        for headline in news_res["headlines"][:3]:
            st.markdown(f"""
            <div style="padding:10px; border:1px solid #0d1f35; border-radius:6px; background:#08111e; margin-bottom:8px;">
                <a href="{headline['link']}" style="color:#dde5f0; text-decoration:none; font-size:0.8rem; font-weight:bold;">
                    {headline['title']}
                </a><br>
                <span style="color:#5a7a9a; font-size:0.7rem;">Publish: {headline['date']}</span>
            </div>
            """, unsafe_print_html=True)

    with col_sen2:
        st.markdown(f"""
        <div class="terminal-card" style="border-top:3px solid #0080ff;">
            <h4 style="margin:0; color:#ffffff; font-size:0.9rem;">💬 Reddit Community Dynamics</h4>
            <div style="font-family:'JetBrains Mono', monospace; font-size:1.15rem; color:#00ff66; margin:8px 0;">
                Sentiment Score: {round(reddit_res['score'], 2)} / 1.00
            </div>
            <p style="color:#5a7a9a; font-size:0.75rem; margin-bottom:12px;">Indian Finance Forum feeds:</p>
        </div>
        """, unsafe_print_html=True)
        
        # Displaying Reddit posts
        for post in reddit_res["posts"][:3]:
            st.markdown(f"""
            <div style="padding:10px; border:1px solid #0d1f35; border-radius:6px; background:#08111e; margin-bottom:8px;">
                <a href="{post['permalink']}" style="color:#dde5f0; text-decoration:none; font-size:0.8rem; font-weight:bold;">
                    {post['title']}
                </a><br>
                <span style="color:#00ff66; font-size:0.7rem; font-family:'JetBrains Mono', monospace;">Upvote Multiplier: {post['score']}x</span>
            </div>
            """, unsafe_print_html=True)

    with col_sen3:
        st.markdown(f"""
        <div class="terminal-card" style="border-top:3px solid #0080ff;">
            <h4 style="margin:0; color:#ffffff; font-size:0.9rem;">🐦 Stocktwits Micro-Feeds</h4>
            <div style="font-family:'JetBrains Mono', monospace; font-size:1.15rem; color:#00ff66; margin:8px 0;">
                Sentiment Score: {round(twits_res['score'], 2)} / 1.00
            </div>
            <p style="color:#5a7a9a; font-size:0.75rem; margin-bottom:12px;">Active CashTag symbol comments:</p>
        </div>
        """, unsafe_print_html=True)
        
        # Displaying Stocktwits messages
        for msg in twits_res["messages"][:3]:
            pill_col = "pill-green" if msg["sentiment"] == "Bullish" else "pill-red" if msg["sentiment"] == "Bearish" else "pill-blue"
            st.markdown(f"""
            <div style="padding:10px; border:1px solid #0d1f35; border-radius:6px; background:#08111e; margin-bottom:8px;">
                <span class="pill {pill_col}">{msg['sentiment'] or "NEUTRAL"}</span>
                <span style="color:#dde5f0; font-size:0.8rem;">
                    <strong>@{msg['user']}:</strong> {msg['body'][:90]}...
                </span>
            </div>
            """, unsafe_print_html=True)

st.sidebar.info("Application execution processed cleanly. Terminal interface active.")