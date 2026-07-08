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

    # --- Supertrend (10, 3) ---
    hl2 = (high + low) / 2
    tr_st = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr_st = tr_st.ewm(alpha=1/10, adjust=False).mean()
    upperband = hl2 + (3.0 * atr_st)
    lowerband = hl2 - (3.0 * atr_st)

    upperband_list = upperband.tolist()
    lowerband_list = lowerband.tolist()
    close_list = close.tolist()
    supertrend_list = [0.0] * len(df)
    direction_list = [1] * len(df)
    
    for i in range(1, len(df)):
        if close_list[i-1] > upperband_list[i-1]:
            pass
        else:
            upperband_list[i] = min(upperband_list[i], upperband_list[i-1])
            
        if close_list[i-1] < lowerband_list[i-1]:
            pass
        else:
            lowerband_list[i] = max(lowerband_list[i], lowerband_list[i-1])
            
        if close_list[i] > upperband_list[i-1]:
            direction_list[i] = 1
        elif close_list[i] < lowerband_list[i-1]:
            direction_list[i] = -1
        else:
            direction_list[i] = direction_list[i-1]
            if direction_list[i] == 1 and lowerband_list[i] < lowerband_list[i-1]:
                lowerband_list[i] = lowerband_list[i-1]
            if direction_list[i] == -1 and upperband_list[i] > upperband_list[i-1]:
                upperband_list[i] = upperband_list[i-1]
                
        if direction_list[i] == 1:
            supertrend_list[i] = lowerband_list[i]
        else:
            supertrend_list[i] = upperband_list[i]
            
    df['Supertrend'] = supertrend_list
    df['ST_Direction'] = direction_list
    
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
