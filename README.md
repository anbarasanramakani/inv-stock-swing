# NSE Pulse — Swing Trade Professional Terminal

`NSE Pulse` is a self-contained, real-time swing trading terminal for the Indian stock market (NSE). It scans multiple stock universes (Nifty 50, Nifty 100, Nifty 500, Nifty 1000, and F&O) for technical setups, crosses them with institutional bulk deals and live news catalysts, and tracks performance with a built-in historical backtester.

---

## 📂 Codebase Directory & Architecture

```
inv-stock-swing/
├── app.py                            # Streamlit web app layout, custom terminal styles & reactive logic
├── data_provider.py                  # Data fetcher: historical (yfinance) and live (nsepython + NSE JSON API)
├── tickers.py                        # Constituent lists (Nifty 50, 100, 500, 1000, F&O) and delisting filters
├── screeners.py                      # Math engines for indicators (EMAs, RSI, MACD, VWAP, BB) and swing setups
├── institutional.py                  # Web parser for FII net flows, MF/FPI bulk deals, and HFT exclusions
├── news_provider.py                  # Live Google News RSS scraper and event-driven backtesting
├── generate_historical_backtests.py  # Utility to compile 10-day backtest cache (Opt. & Tier-1)
├── generate_long_term_backtests.py   # Utility to compile 2-month backtest cache (Medium-term)
├── requirements.txt                  # Python dependencies
└── *.csv                             # Pre-compiled backtest caches used by the UI
```

---

## ⚙️ How to Start the App

### 1. Install Dependencies
Make sure you have Python 3.10+ installed. Install the pinned dependencies from the workspace root:
```bash
pip install -r requirements.txt
```

### 2. Generate/Update Backtest Caches (Optional but Recommended)
To pre-compile historical performance metrics for the UI:
```bash
python generate_historical_backtests.py
python generate_long_term_backtests.py
```

### 3. Launch the Terminal UI
Start the Streamlit server:
```bash
streamlit run app.py
```
Open **`http://localhost:8501`** in your web browser.

---

## ⚡ Execution Flow (Run Full Analysis)

When you choose a universe/strategy and click **"Run Full Analysis"** in the sidebar:
1. **Symbol Resolution**: `tickers.py` returns the target list of `.NS` symbols. News catalysts are force-injected to ensure they are evaluated.
2. **Batch Downloader**: `data_provider.py` downloads EOD daily data for the universe in chunks of 100 stocks.
3. **Data Cleaning**: MultiIndex columns are flattened, and rows are coerced to float (handling yfinance anomalies).
4. **Institutional Matching**: `institutional.py` fetches recent bulk deals from the web and filters out algorithmic traders, high-frequency firms, and trades under 5,000 shares to focus on real FII/MF buying.
5. **Technical Screening**: `screeners.py` calculates technical indicators and evaluates strategy entry, stop-loss, and targets.
6. **Live LTP Verification**: The app fetches live prices for all matching picks via `nsepython`'s quote endpoint, falling back to 1-minute yfinance intraday bars.
7. **Rendering**: The UI refreshes with the 3 tabs: Live Picks, Backtest Outcomes, and Deep Chart Analysis.

---

## 🛠️ Module Breakdown (For AI Agents)

### 1. `app.py`
- Main Streamlit layout using a premium dark trading theme (inspired by Bloomberg/GitHub terminal layouts).
- Presents data using HTML/CSS cards instead of basic tables for Today's Picks.
- **Three-tab interface**:
  - `Live Picks & Prices`: Categorizes picks into *Optimized Focus Group*, *Tier-1 (Institutional support)*, *Tier-2 (Technical Momentum)*, *News Catalysts*, and *Medium-Term Swings*.
  - `Backtest Tracker`: Evaluates target hit vs. stop-loss hit outcomes.
  - `Chart Analysis`: Renders a 4-panel interactive Plotly chart (Candlesticks, Volume, RSI, MACD) with an overlay of the live price line.

### 2. `data_provider.py`
- **yfinance >= 0.2.40 Column Flattening**: Modern yfinance returns `MultiIndex(Price, Ticker)` columns even for single stocks. This module extracts data using `df.xs(ticker, axis=1, level=1)` and flattens it to standard `['Close', 'Open', 'High', 'Low', 'Volume']` columns.
- **Live Index API**: Connects directly to `https://www.nseindia.com/api/allIndices` to fetch real-time levels for Nifty 50, Nifty Bank, Nifty IT, Nifty Midcap 100, and Nifty 500.
- **Live LTP**: Tries `nsepython.nse_quote_ltp(symbol)` first for instant NSE quotes. Falls back to downloading 1-day/1-minute interval bars from yfinance.

### 3. `tickers.py`
- Excludes delisted companies (e.g. ADANITRANS, PEL, ZOMATO is updated to ETERNAL).
- Defines a high-liquidity F&O universe (~177 liquid stocks) which is ideal for swing and intraday scanning.

### 4. `screeners.py`
- **Indicator Formulas**:
  - `EMA(N)`: Exponential Moving Average.
  - `RSI(14)`: Relative Strength Index.
  - `MACD`: MACD line, Signal line, and MACD Histogram.
  - `VWAP`: Cumulative Typical Price * Volume / Cumulative Volume.
  - `ATR(14)`: Average True Range (used to define dynamic target/stop-loss buffers).
- **Core Short-Term Strategies** (5-day hold):
  - `EMA Pullback (20)`: Price touches or dips below EMA 20 in an uptrend, with high volume.
  - `RSI Reversal & Pullback`: RSI oversold (< 30) or pulling back to the 50 level in an uptrend.
  - `Volume Breakout`: Current volume > 2.5x of the 20-day average volume.
  - `MACD Crossover`: MACD histogram crosses above 0.
  - `Bollinger Rebound`: Price touches the lower Bollinger Band and begins turning upward.
- **Medium-Term Swing Strategy** (15-day to 1-month hold):
  - Looks for EMA 20/50 crossovers or Bollinger Band squeeze breakouts.

### 5. `institutional.py`
- Scrapes FII/FPI activity levels.
- **Institutional Screening Guard**: Employs exact string matching to exclude algorithmic trading firms, high-frequency desks (e.g., "HRT", "ALGO", "GRAVITON", "XTX"), and retail traders. Focuses exclusively on known mutual funds, insurance companies, and institutional pension funds.

### 6. `news_provider.py`
- Scrapes the Google News RSS feed for positive swing catalysts (e.g., "earnings beat", "order win", "acquisition").
- Scores and screens sentiment, returning entry suggestions for stocks with active catalysts.

---

## 📈 Technical Indicators Reference

- **VWAP**: Used as a live intraday filter. A price above VWAP indicates daily strength.
- **MACD Crossover**: Requires `MACD_Hist` to cross above `0` (momentum shift confirmation).
- **Volume Ratio**: Defined as `Volume / Vol_Avg20`. A ratio > 1.5 indicates strong institutional participation.
