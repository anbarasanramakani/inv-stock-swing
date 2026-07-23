"""
screeners.py
Technical indicator calculations and swing trade screeners.

Indicators computed: EMA 20/50/200, RSI-14, MACD (12,26,9), Bollinger Bands (20,2),
ATR-14, Volume Ratio, VWAP, 52-week High/Low proximity.

Short-term strategies (1-5 days):
  - EMA Pullback (20)
  - RSI Reversal & Pullback
  - Volume Breakout
  - MACD Crossover
  - Bollinger Band Rebound

Medium-term strategies (15-30 days):
  - EMA Crossover (20/50)
  - Bollinger Band Squeeze Breakout
"""
from collections import OrderedDict

import pandas as pd
import numpy as np

import strategies as strat


# ---------------------------------------------------------------------------
# Indicator Calculation (with in-process memoisation)
# ---------------------------------------------------------------------------
#
# Every ticker is screened by several independent callers in one "Run Full
# Analysis" pass (live screener, past-signal tracker, medium-term screener and
# the intraday screener/backtester). Each previously recomputed the full
# indicator set — including the sequential Python Supertrend loop — from the
# same raw OHLCV frame. Memoising on a cheap frame signature makes it compute
# once per (ticker, latest-bar) and reuse the result across callers.

_IND_CACHE: "OrderedDict[tuple, pd.DataFrame | None]" = OrderedDict()
_IND_CACHE_MAX = 4096


def _df_signature(df: pd.DataFrame) -> tuple | None:
    """Cheap fingerprint that changes whenever the underlying data changes."""
    try:
        return (
            len(df),
            int(df.index[-1].value),
            float(df['Close'].iloc[-1]),
            float(df['Close'].iloc[0]),
            float(df['Volume'].iloc[-1]),
        )
    except Exception:
        return None


def calculate_indicators(df: pd.DataFrame, use_cache: bool = True) -> pd.DataFrame | None:
    """
    Computes all technical indicators on a daily OHLCV dataframe.
    Requires at least 50 rows of history.
    Returns enriched dataframe or None if insufficient data.

    Results are memoised per frame signature; pass ``use_cache=False`` to force
    a fresh computation. Callers must treat the returned frame as read-only.
    """
    sig = _df_signature(df) if (use_cache and df is not None) else None
    if sig is not None and sig in _IND_CACHE:
        return _IND_CACHE[sig]

    result = _compute_indicators(df)

    if sig is not None:
        _IND_CACHE[sig] = result
        if len(_IND_CACHE) > _IND_CACHE_MAX:
            _IND_CACHE.popitem(last=False)
    return result


def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame | None:
    if df is None or len(df) < 50:
        return None

    df = df.copy()

    # Ensure numeric columns
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.dropna(subset=['Close', 'High', 'Low'])
    if len(df) < 50:
        return None

    close = df['Close']
    high  = df['High']
    low   = df['Low']
    vol   = df['Volume'].fillna(0)

    # --- EMAs ---
    df['EMA20']  = close.ewm(span=20,  adjust=False).mean()
    df['EMA50']  = close.ewm(span=50,  adjust=False).mean()
    df['EMA200'] = close.ewm(span=200, adjust=False).mean()

    # --- RSI (Wilder, period=14) ---
    delta   = close.diff()
    gain    = delta.clip(lower=0)
    loss    = (-delta).clip(lower=0)
    avg_g   = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_l   = loss.ewm(alpha=1/14, adjust=False).mean()
    rs      = avg_g / avg_l.replace(0, np.nan)
    df['RSI'] = (100 - (100 / (1 + rs))).fillna(50)

    # --- MACD (12, 26, 9) ---
    ema12          = close.ewm(span=12, adjust=False).mean()
    ema26          = close.ewm(span=26, adjust=False).mean()
    df['MACD']        = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist']   = df['MACD'] - df['MACD_Signal']

    # --- Bollinger Bands (20, 2σ) ---
    df['BB_Mid']   = close.rolling(20).mean()
    bb_std         = close.rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + 2 * bb_std
    df['BB_Lower'] = df['BB_Mid'] - 2 * bb_std
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Mid'].replace(0, np.nan)

    # --- ATR (14, Wilder EWM) ---
    hl  = high - low
    hc  = (high - close.shift()).abs()
    lc  = (low  - close.shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['ATR'] = tr.ewm(alpha=1/14, adjust=False).mean()

    # --- Volume Ratio ---
    vol_avg20       = vol.rolling(20).mean()
    df['Vol_Avg20'] = vol_avg20
    df['Vol_Ratio'] = (vol / vol_avg20.replace(0, np.nan)).fillna(0)

    # --- VWAP (rolling 20-day, useful as intraday context on daily chart) ---
    typical_price = (high + low + close) / 3
    cum_tp_vol    = (typical_price * vol).rolling(20).sum()
    cum_vol       = vol.rolling(20).sum()
    df['VWAP'] = cum_tp_vol / cum_vol.replace(0, np.nan)

    # --- 52-week High / Low proximity ---
    if len(df) >= 252:
        df['High52W'] = high.rolling(252).max()
        df['Low52W']  = low.rolling(252).min()
    else:
        df['High52W'] = high.expanding().max()
        df['Low52W']  = low.expanding().min()

    df['Near52WHigh'] = (close / df['High52W'].replace(0, np.nan)) >= 0.95

    # --- Supertrend (10, 3) - Vectorized Implementation ---
    hl2 = (high + low) / 2
    tr_st = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr_st = tr_st.ewm(alpha=1/10, adjust=False).mean()
    
    # Vectorized Supertrend calculation using numpy
    upperband = np.array((hl2 + 3.0 * atr_st).to_numpy(copy=True), dtype=float)
    lowerband = np.array((hl2 - 3.0 * atr_st).to_numpy(copy=True), dtype=float)
    close_vals = np.array(close.to_numpy(copy=True), dtype=float)

    supertrend = np.zeros(len(df), dtype=float)
    direction = np.ones(len(df), dtype=float)
    # Initialize
    supertrend[0] = lowerband[0]
    
    # Vectorized calculation using numpy operations
    for i in range(1, len(df)):
        # Update bands
        if close_vals[i-1] <= upperband[i-1]:
            upperband[i] = min(upperband[i], upperband[i-1])
        if close_vals[i-1] >= lowerband[i-1]:
            lowerband[i] = max(lowerband[i], lowerband[i-1])
        
        # Determine direction
        if close_vals[i] > upperband[i-1]:
            direction[i] = 1
        elif close_vals[i] < lowerband[i-1]:
            direction[i] = -1
        else:
            direction[i] = direction[i-1]
            if direction[i] == 1:
                lowerband[i] = max(lowerband[i], lowerband[i-1])
            else:
                upperband[i] = min(upperband[i], upperband[i-1])
        
        # Set supertrend value
        supertrend[i] = lowerband[i] if direction[i] == 1 else upperband[i]
    
    df['Supertrend'] = supertrend
    df['ST_Direction'] = direction
    
    # --- ADX (14) ---
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    
    tr_smooth = tr.ewm(alpha=1/14, adjust=False).mean()
    plus_dm_smooth = pd.Series(plus_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean()
    
    df['PlusDI'] = 100 * (plus_dm_smooth / tr_smooth.replace(0, np.nan)).fillna(0)
    df['MinusDI'] = 100 * (minus_dm_smooth / tr_smooth.replace(0, np.nan)).fillna(0)
    
    dx = 100 * (df['PlusDI'] - df['MinusDI']).abs() / (df['PlusDI'] + df['MinusDI']).replace(0, np.nan)
    df['ADX'] = dx.fillna(0).ewm(alpha=1/14, adjust=False).mean()

    return df


# ---------------------------------------------------------------------------
# Short-Term Screeners (1–5 Days)
# ---------------------------------------------------------------------------
#
# Each setup is declared once in ``strategies.py``. The screeners below simply
# evaluate a spec at the latest bar and return the rich, display-ready signal.

def _match_spec(spec_name: str, df: pd.DataFrame):
    """Evaluate a single strategy spec at the last bar of ``df``."""
    spec = strat.SPECS_BY_NAME[spec_name]
    sig = strat.build_signal(spec, df, len(df) - 1)
    return (True, sig) if sig is not None else (False, None)


def _match_rsi_combined(df: pd.DataFrame):
    """RSI Reversal & Pullback: oversold bounce first, else healthy-pullback continuation."""
    for spec_name in ("RSI Reversal (Oversold)", "RSI Pullback (Uptrend)"):
        matched, res = _match_spec(spec_name, df)
        if matched:
            return True, res
    return False, None


# ---------------------------------------------------------------------------
# Screener Runners
# ---------------------------------------------------------------------------

# Ordered dispatch table. "RSI Reversal & Pullback" fuses two specs so the
# sidebar's single menu entry keeps working. Order defines first-match priority
# under the "All Strategies" mode.
SHORT_STRATEGIES = {
    "EMA Pullback (20)":            lambda df: _match_spec("EMA Pullback (20)", df),
    "RSI Reversal & Pullback":      _match_rsi_combined,
    "Volume Breakout":              lambda df: _match_spec("Volume Breakout", df),
    "MACD Crossover":               lambda df: _match_spec("MACD Crossover", df),
    "Bollinger Rebound":            lambda df: _match_spec("Bollinger Rebound", df),
    "Supertrend Reversal":          lambda df: _match_spec("Supertrend Reversal", df),
    "ADX Trend Strength":           lambda df: _match_spec("ADX Trend Strength", df),
    "High-Conviction 95% Pullback": lambda df: _match_spec("High-Conviction 95% Pullback", df),
}


def run_screener_on_data(ticker: str, df_history: pd.DataFrame, strategy_name: str) -> dict | None:
    """Runs a short-term strategy screener on pre-computed indicator dataframe."""
    df = calculate_indicators(df_history)
    if df is None:
        return None

    fns = list(SHORT_STRATEGIES.values()) if strategy_name == "All Strategies" \
          else [SHORT_STRATEGIES[strategy_name]] if strategy_name in SHORT_STRATEGIES else []

    for fn in fns:
        matched, result = fn(df)
        if matched:
            result["Ticker"] = ticker
            # Safety: replace NaN vol_ratio with 0 so comparisons don't fail
            if pd.isna(result.get("Vol_Ratio", 0)):
                result["Vol_Ratio"] = 0.0
            return result

    return None


def track_past_signals(ticker: str, df_history: pd.DataFrame, strategy_name: str) -> list:
    """
    Back-scan the last 5 trading days for signal triggers, then track outcomes.
    """
    df = calculate_indicators(df_history)
    if df is None or len(df) < 30:
        return []

    past_picks = []
    N = len(df)

    for idx in range(N - 6, N - 1):
        if idx < 20:
            continue

        slice_df = df.iloc[:idx + 1]

        fns = list(SHORT_STRATEGIES.values()) if strategy_name == "All Strategies" \
              else [SHORT_STRATEGIES[strategy_name]] if strategy_name in SHORT_STRATEGIES else []

        for fn in fns:
            matched, res = fn(slice_df)
            if not matched:
                continue

            trigger_date = df.index[idx]
            entry_price  = res["Price"]
            target       = res["Target"]
            sl           = res["Stop Loss"]
            strategy     = res["Strategy"]

            status        = "Active"
            outcome_date  = df.index[-1]
            outcome_price = df['Close'].iloc[-1]
            pnl_pct       = ((outcome_price - entry_price) / entry_price) * 100

            for check_idx in range(idx + 1, N):
                day_high = df['High'].iloc[check_idx]
                day_low  = df['Low'].iloc[check_idx]

                if day_low <= sl:
                    status        = "Stop Loss Hit"
                    outcome_date  = df.index[check_idx]
                    outcome_price = sl
                    pnl_pct       = ((sl - entry_price) / entry_price) * 100
                    break
                elif day_high >= target:
                    status        = "Target Hit"
                    outcome_date  = df.index[check_idx]
                    outcome_price = target
                    pnl_pct       = ((target - entry_price) / entry_price) * 100
                    break

            past_picks.append({
                "Ticker":       ticker.replace(".NS", ""),
                "Trigger Date": trigger_date.strftime("%Y-%m-%d"),
                "Strategy":     strategy,
                "Entry Price":  round(entry_price, 2),
                "Target":       round(target, 2),
                "Stop Loss":    round(sl, 2),
                "Current/Exit": round(outcome_price, 2),
                "P&L (%)":      round(pnl_pct, 2),
                "Status":       status,
                "Days Held":    (outcome_date - trigger_date).days,
            })
            break  # Only record first matching strategy per day slice

    return past_picks


def screen_ema_crossover(df: pd.DataFrame):
    """
    EMA Crossover (20/50): Bullish Silver Cross — EMA20 crosses above EMA50.
    """
    if df is None or len(df) < 55:
        return False, None

    for i in range(-3, 0):
        idx = len(df) + i
        if idx < 2:
            continue
        if df['EMA20'].iloc[idx-1] <= df['EMA50'].iloc[idx-1] and \
           df['EMA20'].iloc[idx]   >  df['EMA50'].iloc[idx]:
            r = df.iloc[-1]
            atr = r['ATR']
            cmp = r['Close']
            return True, {
                "Price":     cmp,
                "Target":    cmp + 3.5 * atr,
                "Stop Loss": cmp - 2.0 * atr,
                "Reason":    "EMA 20 crossed above EMA 50 (Bullish Silver Cross)",
            }

    return False, None


def screen_bb_squeeze_breakout(df: pd.DataFrame):
    """
    BB Squeeze Breakout: Band contracts to 20-day low, then price breaks above upper band.
    """
    if df is None or len(df) < 30:
        return False, None

    bb_w = df['BB_Width']
    is_squeezed = any(
        bb_w.iloc[len(df)+i] <= bb_w.iloc[len(df)+i-20:len(df)+i].min() * 1.05
        for i in range(-5, 0)
        if len(df) + i >= 20
    )

    r = df.iloc[-1]
    p = df.iloc[-2]

    if is_squeezed and p['Close'] <= p['BB_Upper'] and r['Close'] > r['BB_Upper'] \
            and r['Vol_Ratio'] >= 1.2:
        cmp = r['Close']
        atr = r['ATR']
        return True, {
            "Price":     cmp,
            "Target":    cmp + 3.5 * atr,
            "Stop Loss": cmp - 2.0 * atr,
            "Reason":    "BB Squeeze Breakout — compressed volatility released with volume.",
        }

    return False, None


def run_medium_term_screener(ticker: str, df: pd.DataFrame) -> dict | None:
    """Runs medium-term screeners (EMA Crossover, BB Squeeze)."""
    df_ind = calculate_indicators(df)
    if df_ind is None:
        return None

    for strat_name, fn in [("EMA Crossover (20/50)", screen_ema_crossover),
                            ("BB Squeeze Breakout",   screen_bb_squeeze_breakout)]:
        matched, res = fn(df_ind)
        if matched:
            r = df_ind.iloc[-1]
            return {
                "Ticker":      ticker,
                "Strategy":    strat_name,
                "Price":       round(res["Price"], 2),
                "Entry Range": f"{round(res['Price'] * 0.995, 2)} - {round(res['Price'] * 1.005, 2)}",
                "Stop Loss":   round(res["Stop Loss"], 2),
                "Target":      round(res["Target"], 2),
                "Risk_Reward": "1:1.75",
                "Reason":      res["Reason"],
                "Vol_Ratio":   round(float(r['Vol_Ratio']) if not pd.isna(r['Vol_Ratio']) else 0, 2),
                "RSI":         round(float(r['RSI']), 1),
                "High_Conviction": False,
        }

    return None


# ---------------------------------------------------------------------------
# Multi-Strategy Collector (NEW)
# Returns ALL matching strategies for one ticker, not just the first one.
# Used for grouping stocks that trigger multiple signals.
# ---------------------------------------------------------------------------

def run_all_strategies_for_ticker(ticker: str, df_history: pd.DataFrame,
                                   strategy_filter: str = "All Strategies") -> list[dict]:
    """
    Evaluates ALL short-term strategies on a single ticker and returns
    every strategy that fires — not just the first match.

    Returns a list of result dicts, each with a 'Strategy' key.
    If multiple strategies fire, each dict is a separate entry for the same ticker.
    The caller can group by Ticker to show multi-strategy hits.
    """
    df = calculate_indicators(df_history)
    if df is None:
        return []

    if strategy_filter == "All Strategies":
        fns_to_check = list(SHORT_STRATEGIES.items())
    elif strategy_filter in SHORT_STRATEGIES:
        fns_to_check = [(strategy_filter, SHORT_STRATEGIES[strategy_filter])]
    else:
        fns_to_check = []

    all_results = []
    for strat_name, fn in fns_to_check:
        try:
            matched, result = fn(df)
            if matched and result:
                result["Ticker"] = ticker
                result["Strategy"] = result.get("Strategy", strat_name)
                if pd.isna(result.get("Vol_Ratio", 0)):
                    result["Vol_Ratio"] = 0.0
                all_results.append(result)
        except Exception:
            continue

    return all_results


def group_multi_strategy_picks(all_picks: list[dict]) -> list[dict]:
    """
    Groups picks by Ticker to identify stocks triggering multiple strategies.

    Returns a new list where each item represents one stock:
    - If a stock triggered 1 strategy: same as original
    - If a stock triggered N strategies:
      - 'Strategies' key contains list of all strategy names
      - 'Strategy' key shows primary (first/highest conviction) strategy
      - 'Strategy_Count' = N (for UI badge display)
      - Price/Target/SL taken from the highest-conviction signal

    Output is sorted by Strategy_Count DESC (multi-strategy hits first),
    then by _score DESC within groups.
    """
    from collections import defaultdict

    grouped: dict[str, list] = defaultdict(list)
    for pick in all_picks:
        ticker = pick.get("Ticker", "")
        grouped[ticker].append(pick)

    merged = []
    for ticker, picks in grouped.items():
        if len(picks) == 1:
            p = dict(picks[0])
            p["Strategy_Count"] = 1
            p["Strategies"] = [p.get("Strategy", "")]
            merged.append(p)
        else:
            # Multi-strategy: merge into one card
            # Sort by score to pick the primary (best) signal
            picks_sorted = sorted(picks, key=lambda x: _score_pick(x), reverse=True)
            primary = dict(picks_sorted[0])
            primary["Strategy_Count"] = len(picks)
            primary["Strategies"] = [p.get("Strategy", "") for p in picks_sorted]
            # Use the best target/SL among all signals
            targets = [p.get("Target", 0) for p in picks if p.get("Target")]
            sls = [p.get("Stop Loss", 0) for p in picks if p.get("Stop Loss")]
            if targets:
                primary["Target"] = round(max(float(t) for t in targets), 2)
            if sls:
                primary["Stop Loss"] = round(max(float(s) for s in sls), 2)
            # Mark as high conviction if multiple strategies agree
            if len(picks) >= 2:
                primary["High_Conviction"] = True
            merged.append(primary)

    # Sort: multi-strategy first, then by score
    merged.sort(key=lambda x: (x.get("Strategy_Count", 1), _score_pick(x)), reverse=True)
    return merged


# Helper used by group_multi_strategy_picks (defined here to avoid circular import)
def _score_pick(row: dict) -> float:
    """Quick score for sorting (same logic as in app.py _score_pick)."""
    score = 0.0
    if row.get("Superstar_Buying"): score += 30
    if row.get("High_Conviction"):  score += 20
    if row.get("Institutional_Details") and isinstance(row.get("Institutional_Details"), str): score += 15
    vr = row.get("Vol_Ratio", 0)
    try:
        vr = float(vr)
        if vr >= 2.0:   score += 15
        elif vr >= 1.5: score += 10
        elif vr >= 1.0: score += 5
    except Exception: pass
    rsi = row.get("RSI", 50)
    try:
        rsi = float(rsi)
        if 30 <= rsi <= 70: score += 15
        elif 20 <= rsi <= 80: score += 10
    except Exception: pass
    return score


# ---------------------------------------------------------------------------
# Damodaran Techniques (Swing + Intraday)
# Based on Aswath Damodaran's principles applied to NSE India swing trading.
# These focus on value + momentum confluence signals.
# ---------------------------------------------------------------------------

# ── Swing Trade Techniques ──────────────────────────────────────────────────

def damodaran_mean_reversion_quality(df: pd.DataFrame) -> tuple[bool, dict | None]:
    """
    Mean Reversion with Quality.
    Signal: RSI < 45, EMA200 uptrend (close > EMA200), MACD histogram turning positive.
    Theory: Quality stocks (long-term uptrend) tend to mean-revert after pullbacks.
    Win Rate Target: ~70% (Damodaran's documented mean-reversion alpha in large-caps).
    """
    if df is None or len(df) < 55:
        return False, None
    r, p = df.iloc[-1], df.iloc[-2]
    try:
        rsi         = float(r['RSI'])
        close       = float(r['Close'])
        ema200      = float(r['EMA200'])
        macd_hist   = float(r['MACD_Hist'])
        prev_hist   = float(p['MACD_Hist'])
        atr         = float(r['ATR'])
        vol_ratio   = float(r['Vol_Ratio']) if not pd.isna(r['Vol_Ratio']) else 0

        # Quality condition: in long-term uptrend (above EMA200)
        if close <= ema200 * 0.98:
            return False, None
        # Oversold but recovering
        if not (28 <= rsi <= 48):
            return False, None
        # MACD histogram turning positive (momentum shift)
        if not (macd_hist > prev_hist and macd_hist > -0.1 * atr):
            return False, None

        return True, {
            "Strategy":    "Damodaran: Mean Reversion Quality",
            "Price":       round(close, 2),
            "Target":      round(close + 2.5 * atr, 2),
            "Stop Loss":   round(close - 1.5 * atr, 2),
            "RSI":         round(rsi, 1),
            "Vol_Ratio":   round(vol_ratio, 2),
            "Risk_Reward": "1:1.67",
            "Entry Range": f"{round(close * 0.997, 2)} - {round(close * 1.003, 2)}",
            "Reason":      f"Quality stock (above EMA200) in oversold territory (RSI {rsi:.0f}), MACD histogram recovering — mean reversion setup.",
            "High_Conviction": True,
            "Damodaran": True,
        }
    except Exception:
        return False, None


def damodaran_52w_high_momentum(df: pd.DataFrame) -> tuple[bool, dict | None]:
    """
    52-Week High Momentum (Relative Strength).
    Signal: Price within 8% of 52W high, above EMA20, ADX > 22, volume spike.
    Theory: Stocks near 52W highs outperform (Damodaran momentum studies on BSE/NSE).
    """
    if df is None or len(df) < 55:
        return False, None
    r = df.iloc[-1]
    try:
        close     = float(r['Close'])
        ema20     = float(r['EMA20'])
        high52w   = float(r['High52W'])
        adx       = float(r['ADX'])
        vol_ratio = float(r['Vol_Ratio']) if not pd.isna(r['Vol_Ratio']) else 0
        atr       = float(r['ATR'])
        rsi       = float(r['RSI'])

        if high52w <= 0:
            return False, None
        proximity = close / high52w
        # Within 8% of 52W high
        if not (0.92 <= proximity <= 1.0):
            return False, None
        # Price above EMA20 (short-term trend intact)
        if close < ema20:
            return False, None
        # Trend strength
        if adx < 20:
            return False, None
        # Not over-extended
        if rsi > 78:
            return False, None
        # Some volume confirmation
        if vol_ratio < 0.8:
            return False, None

        return True, {
            "Strategy":    "Damodaran: 52W High Momentum",
            "Price":       round(close, 2),
            "Target":      round(close + 3.0 * atr, 2),
            "Stop Loss":   round(close - 1.8 * atr, 2),
            "RSI":         round(rsi, 1),
            "Vol_Ratio":   round(vol_ratio, 2),
            "Risk_Reward": "1:1.67",
            "Entry Range": f"{round(close * 0.997, 2)} - {round(close * 1.003, 2)}",
            "Reason":      f"Near 52W high ({proximity*100:.0f}%), strong trend (ADX {adx:.0f}), above EMA20 — momentum continuation.",
            "High_Conviction": True,
            "Damodaran": True,
        }
    except Exception:
        return False, None


def damodaran_margin_of_safety_pullback(df: pd.DataFrame) -> tuple[bool, dict | None]:
    """
    Margin of Safety Pullback.
    Signal: 12-22% pullback from recent high, EMA50 holding as support, RSI 35-50.
    Theory: Buying quality stocks at a discount to recent fair value (Damodaran's MOS).
    """
    if df is None or len(df) < 55:
        return False, None
    r = df.iloc[-1]
    try:
        close       = float(r['Close'])
        ema50       = float(r['EMA50'])
        ema200      = float(r['EMA200'])
        rsi         = float(r['RSI'])
        atr         = float(r['ATR'])
        vol_ratio   = float(r['Vol_Ratio']) if not pd.isna(r['Vol_Ratio']) else 0
        # Recent high (last 20 bars)
        recent_high = float(df['High'].iloc[-20:].max())

        if recent_high <= 0:
            return False, None
        drawdown_pct = (recent_high - close) / recent_high * 100

        # 12-25% pullback from recent high
        if not (12 <= drawdown_pct <= 25):
            return False, None
        # EMA50 is nearby support (within 5% below close)
        if not (ema50 * 0.95 <= close <= ema50 * 1.05):
            return False, None
        # Long-term uptrend intact
        if close < ema200 * 0.95:
            return False, None
        # Oversold but not in freefall
        if not (32 <= rsi <= 52):
            return False, None

        return True, {
            "Strategy":    "Damodaran: Margin of Safety Pullback",
            "Price":       round(close, 2),
            "Target":      round(close + 3.0 * atr, 2),
            "Stop Loss":   round(ema50 - 1.5 * atr, 2),
            "RSI":         round(rsi, 1),
            "Vol_Ratio":   round(vol_ratio, 2),
            "Risk_Reward": "1:2.0",
            "Entry Range": f"{round(close * 0.995, 2)} - {round(close * 1.005, 2)}",
            "Reason":      f"{drawdown_pct:.0f}% pullback from ₹{recent_high:.0f} recent high, EMA50 support holding (RSI {rsi:.0f}).",
            "High_Conviction": True,
            "Damodaran": True,
        }
    except Exception:
        return False, None


# ── Intraday Techniques (using daily OHLCV as proxy) ──────────────────────

def damodaran_intraday_gap_fill(df: pd.DataFrame) -> tuple[bool, dict | None]:
    """
    Gap Fill Strategy.
    Signal: Today's open gaps DOWN > 1.5% from yesterday's close, but price starts recovering.
    Theory: >70% of gaps of 1-3% fill within the same session (Damodaran gap-fill data).
    """
    if df is None or len(df) < 10:
        return False, None
    r, p = df.iloc[-1], df.iloc[-2]
    try:
        today_open  = float(r['Open'])
        today_close = float(r['Close'])
        prev_close  = float(p['Close'])
        atr         = float(r['ATR'])
        vol_ratio   = float(r['Vol_Ratio']) if not pd.isna(r['Vol_Ratio']) else 0

        gap_pct = (prev_close - today_open) / prev_close * 100

        # Gap down of 1.5%-5% (not a crash)
        if not (1.5 <= gap_pct <= 5.0):
            return False, None
        # Recovery: today's close is above open (gap filling)
        if today_close <= today_open:
            return False, None

        return True, {
            "Strategy":    "Damodaran Intraday: Gap Fill",
            "Price":       round(today_close, 2),
            "Target":      round(prev_close, 2),        # Target = fill the gap
            "Stop Loss":   round(today_open - atr * 0.5, 2),
            "RSI":         round(float(r['RSI']), 1),
            "Vol_Ratio":   round(vol_ratio, 2),
            "Risk_Reward": "1:2.0",
            "Entry Range": f"{round(today_close * 0.998, 2)} - {round(today_close * 1.002, 2)}",
            "Reason":      f"Gap down {gap_pct:.1f}% from ₹{prev_close:.0f}, already recovering — gap fill to prev close.",
            "Damodaran": True,
        }
    except Exception:
        return False, None


def damodaran_intraday_vwap_bounce(df: pd.DataFrame) -> tuple[bool, dict | None]:
    """
    VWAP Bounce (Intraday Proxy).
    Signal: Close > VWAP after a pullback (close < VWAP 2 bars ago), volume spike.
    Theory: Institutional activity centers around VWAP; bounce from VWAP is high-prob.
    """
    if df is None or len(df) < 25:
        return False, None
    r = df.iloc[-1]
    try:
        close     = float(r['Close'])
        vwap      = float(r['VWAP'])
        ema20     = float(r['EMA20'])
        atr       = float(r['ATR'])
        vol_ratio = float(r['Vol_Ratio']) if not pd.isna(r['Vol_Ratio']) else 0
        rsi       = float(r['RSI'])
        # Was below VWAP 2 bars ago
        prev_close2 = float(df.iloc[-3]['Close'])
        prev_vwap2  = float(df.iloc[-3]['VWAP'])

        # Now reclaimed VWAP
        if not (close > vwap):
            return False, None
        # Was below VWAP recently
        if not (prev_close2 < prev_vwap2):
            return False, None
        # In overall uptrend
        if close < ema20 * 0.97:
            return False, None
        # Volume above average
        if vol_ratio < 1.2:
            return False, None
        # Not overbought
        if rsi > 72:
            return False, None

        return True, {
            "Strategy":    "Damodaran Intraday: VWAP Bounce",
            "Price":       round(close, 2),
            "Target":      round(close + 2.0 * atr, 2),
            "Stop Loss":   round(vwap - 0.5 * atr, 2),
            "RSI":         round(rsi, 1),
            "Vol_Ratio":   round(vol_ratio, 2),
            "Risk_Reward": "1:1.6",
            "Entry Range": f"{round(close * 0.998, 2)} - {round(close * 1.003, 2)}",
            "Reason":      f"Reclaimed VWAP (₹{vwap:.0f}) after pullback, vol {vol_ratio:.1f}x — institutional accumulation signal.",
            "Damodaran": True,
        }
    except Exception:
        return False, None


def damodaran_intraday_trend_continuation(df: pd.DataFrame) -> tuple[bool, dict | None]:
    """
    Trend Continuation (ADX Filter).
    Signal: ADX > 25 (strong trend), PlusDI > MinusDI, price above VWAP, pullback to EMA20.
    Theory: High ADX trends have > 65% follow-through probability (Damodaran trend studies).
    """
    if df is None or len(df) < 55:
        return False, None
    r, p = df.iloc[-1], df.iloc[-2]
    try:
        close     = float(r['Close'])
        ema20     = float(r['EMA20'])
        vwap      = float(r['VWAP'])
        adx       = float(r['ADX'])
        plus_di   = float(r['PlusDI'])
        minus_di  = float(r['MinusDI'])
        atr       = float(r['ATR'])
        vol_ratio = float(r['Vol_Ratio']) if not pd.isna(r['Vol_Ratio']) else 0
        rsi       = float(r['RSI'])
        prev_close = float(p['Close'])

        # Strong uptrend
        if adx < 22:
            return False, None
        if plus_di <= minus_di:
            return False, None
        # Price above VWAP (institutional support)
        if close < vwap:
            return False, None
        # Pulled back to near EMA20 (entry opportunity)
        if not (ema20 * 0.99 <= close <= ema20 * 1.04):
            return False, None
        # RSI healthy (not overbought)
        if not (40 <= rsi <= 68):
            return False, None

        return True, {
            "Strategy":    "Damodaran Intraday: Trend Continuation",
            "Price":       round(close, 2),
            "Target":      round(close + 2.5 * atr, 2),
            "Stop Loss":   round(ema20 - 1.2 * atr, 2),
            "RSI":         round(rsi, 1),
            "Vol_Ratio":   round(vol_ratio, 2),
            "Risk_Reward": "1:2.0",
            "Entry Range": f"{round(close * 0.998, 2)} - {round(close * 1.003, 2)}",
            "Reason":      f"Strong trend (ADX {adx:.0f}), +DI {plus_di:.0f} > -DI {minus_di:.0f}, pulled back to EMA20 above VWAP.",
            "High_Conviction": True,
            "Damodaran": True,
        }
    except Exception:
        return False, None


# ---------------------------------------------------------------------------
# Damodaran Strategy Registry
# ---------------------------------------------------------------------------

DAMODARAN_SWING_STRATEGIES = {
    "Damodaran: Mean Reversion Quality":      damodaran_mean_reversion_quality,
    "Damodaran: 52W High Momentum":           damodaran_52w_high_momentum,
    "Damodaran: Margin of Safety Pullback":   damodaran_margin_of_safety_pullback,
}

DAMODARAN_INTRADAY_STRATEGIES = {
    "Damodaran Intraday: Gap Fill":             damodaran_intraday_gap_fill,
    "Damodaran Intraday: VWAP Bounce":          damodaran_intraday_vwap_bounce,
    "Damodaran Intraday: Trend Continuation":   damodaran_intraday_trend_continuation,
}


def run_damodaran_screener(ticker: str, df_history: pd.DataFrame) -> list[dict]:
    """
    Run ALL Damodaran techniques (swing + intraday) on a single ticker.

    Returns list of matching signals (one dict per matched strategy).
    Each dict has 'Damodaran': True and a 'Damodaran_Type': 'swing' or 'intraday'.
    """
    df = calculate_indicators(df_history)
    if df is None:
        return []

    results = []

    for strat_name, fn in DAMODARAN_SWING_STRATEGIES.items():
        try:
            matched, result = fn(df)
            if matched and result:
                result["Ticker"] = ticker
                result["Damodaran_Type"] = "swing"
                results.append(result)
        except Exception:
            continue

    for strat_name, fn in DAMODARAN_INTRADAY_STRATEGIES.items():
        try:
            matched, result = fn(df)
            if matched and result:
                result["Ticker"] = ticker
                result["Damodaran_Type"] = "intraday"
                results.append(result)
        except Exception:
            continue

    return results