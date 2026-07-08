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
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Indicator Calculation
# ---------------------------------------------------------------------------

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame | None:
    """
    Computes all technical indicators on a daily OHLCV dataframe.
    Requires at least 50 rows of history.
    Returns enriched dataframe or None if insufficient data.
    """
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
    supertrend = pd.Series(0.0, index=df.index)
    direction = pd.Series(1, index=df.index)
    
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

def screen_ema_pullback(df: pd.DataFrame):
    """
    EMA Pullback (20): Stock in uptrend pulls back to 20 EMA and holds.
    Conditions:
      - Close > EMA50 > EMA200 (strong uptrend)
      - Low touched 20 EMA (within ±1%) and Close recovered above it
      - Bullish or recovering candle
    """
    if df is None or len(df) < 5:
        return False, None

    r = df.iloc[-1]
    p = df.iloc[-2]

    trend_ok   = r['Close'] > r['EMA50'] > r['EMA200']
    pullback_ok = (r['Low'] <= r['EMA20'] * 1.01) and (r['Close'] >= r['EMA20'] * 0.99)
    candle_ok  = r['Close'] >= r['Open'] or r['Close'] > p['Close']

    if not (trend_ok and pullback_ok and candle_ok):
        return False, None

    atr = r['ATR']
    entry = r['Close']
    return True, {
        "Strategy":    "EMA Pullback (20)",
        "Price":       round(entry, 2),
        "RSI":         round(r['RSI'], 1),
        "Vol_Ratio":   round(r['Vol_Ratio'], 2),
        "Entry Range": f"{round(entry * 0.995, 2)} - {round(entry * 1.005, 2)}",
        "Stop Loss":   round(entry - 1.5 * atr, 2),  # Refactored from 1.0 to 1.5
        "Target":      round(entry + 2.0 * atr, 2),  # Refactored from 1.5 to 2.0
        "Risk_Reward": "1:1.33",
        "Reason":      "Uptrend stock touching key 20 EMA support — bounce expected within 1-5 days.",
    }


def screen_rsi_pullback(df: pd.DataFrame):
    """
    RSI Reversal/Pullback: Oversold bounce or healthy RSI pullback in uptrend.
    """
    if df is None or len(df) < 5:
        return False, None

    r = df.iloc[-1]
    p = df.iloc[-2]

    # Case 1: Oversold reversal (RSI crossed above 30 in last 3 bars) + trend filter (Close > EMA200)
    recent_rsi = df['RSI'].iloc[-3:].tolist()
    if recent_rsi[-1] > 30 and any(v < 30 for v in recent_rsi[:-1]) and r['Close'] > r['EMA200']:
        atr = r['ATR']
        entry = r['Close']
        return True, {
            "Strategy":    "RSI Reversal (Oversold)",
            "Price":       round(entry, 2),
            "RSI":         round(r['RSI'], 1),
            "Vol_Ratio":   round(r['Vol_Ratio'], 2),
            "Entry Range": f"{round(entry * 0.99, 2)} - {round(entry * 1.01, 2)}",
            "Stop Loss":   round(entry - 1.0 * atr, 2),
            "Target":      round(entry + 1.8 * atr, 2),  # Refactored from 1.2 to 1.8
            "Risk_Reward": "1:1.80",
            "Reason":      "RSI recovering from oversold in longer-term uptrend.",
        }

    # Case 2: RSI pullback in uptrend (widen range to 38-55, ticking up, above EMA50, vol confirmation)
    trend_ok     = r['Close'] > r['EMA50']
    rsi_pullback = 38 <= r['RSI'] <= 55 and r['RSI'] > p['RSI']
    green_candle = r['Close'] > r['Open']
    vol_ok       = r['Vol_Ratio'] >= 1.1

    if trend_ok and rsi_pullback and green_candle and vol_ok:
        atr = r['ATR']
        entry = r['Close']
        return True, {
            "Strategy":    "RSI Pullback (Uptrend)",
            "Price":       round(entry, 2),
            "RSI":         round(r['RSI'], 1),
            "Vol_Ratio":   round(r['Vol_Ratio'], 2),
            "Entry Range": f"{round(entry * 0.995, 2)} - {round(entry * 1.005, 2)}",
            "Stop Loss":   round(entry - 1.0 * atr, 2),
            "Target":      round(entry + 1.5 * atr, 2),
            "Risk_Reward": "1:1.50",
            "Reason":      "Bullish rebound after healthy pullback in an active trend.",
        }

    return False, None


def screen_volume_breakout(df: pd.DataFrame):
    """
    Volume Breakout: Price at 20-day high with heavy volume (>=2.0x) and above EMA20.
    """
    if df is None or len(df) < 25:
        return False, None

    r = df.iloc[-1]
    price_high20   = df['Close'].iloc[-21:-1].max()
    price_breakout = r['Close'] > price_high20
    volume_spike   = r['Vol_Ratio'] >= 2.0  # Refactored from 1.8 to 2.0
    above_ema20    = r['Close'] > r['EMA20']

    if price_breakout and volume_spike and above_ema20:
        atr = r['ATR']
        entry = r['Close']
        return True, {
            "Strategy":    "Volume Breakout",
            "Price":       round(entry, 2),
            "RSI":         round(r['RSI'], 1),
            "Vol_Ratio":   round(r['Vol_Ratio'], 2),
            "Entry Range": f"{round(entry, 2)} - {round(entry * 1.01, 2)}",
            "Stop Loss":   round(entry - 1.0 * atr, 2),
            "Target":      round(entry + 1.5 * atr, 2),
            "Risk_Reward": "1:1.50",
            "Reason":      "Momentum breakout to fresh highs with heavy institutional volume.",
        }

    return False, None


def screen_macd_crossover(df: pd.DataFrame):
    """
    MACD Crossover: MACD line crosses above Signal — histogram turns positive.
    """
    if df is None or len(df) < 5:
        return False, None

    r = df.iloc[-1]
    p = df.iloc[-2]

    # Crossover: histogram turned positive from negative
    crossed_above = p['MACD_Hist'] <= 0 < r['MACD_Hist']
    near_zero = abs(r['MACD']) < abs(r['Close']) * 0.03
    not_overbought = r['RSI'] < 65

    if crossed_above and near_zero and not_overbought:
        atr = r['ATR']
        entry = r['Close']
        return True, {
            "Strategy":    "MACD Crossover",
            "Price":       round(entry, 2),
            "RSI":         round(r['RSI'], 1),
            "Vol_Ratio":   round(r['Vol_Ratio'], 2),
            "Entry Range": f"{round(entry * 0.995, 2)} - {round(entry * 1.005, 2)}",
            "Stop Loss":   round(entry - 1.0 * atr, 2),
            "Target":      round(entry + 1.5 * atr, 2),  # Refactored from 1.2 to 1.5
            "Risk_Reward": "1:1.50",
            "Reason":      "MACD histogram turned positive — momentum shift confirmed.",
        }

    return False, None


def screen_bollinger_rebound(df: pd.DataFrame):
    """
    Bollinger Band Rebound: Touch lower band → recover inside with green candle.
    """
    if df is None or len(df) < 5:
        return False, None

    r = df.iloc[-1]
    p = df.iloc[-2]

    touched_lower = (p['Low'] <= p['BB_Lower']) or (r['Low'] <= r['BB_Lower'])
    closed_inside = r['Close'] > r['BB_Lower']
    green_candle  = r['Close'] > r['Open']
    trend_ok      = r['Close'] > r['EMA50']

    if touched_lower and closed_inside and green_candle and trend_ok:
        atr = r['ATR']
        entry = r['Close']
        return True, {
            "Strategy":    "Bollinger Rebound",
            "Price":       round(entry, 2),
            "RSI":         round(r['RSI'], 1),
            "Vol_Ratio":   round(r['Vol_Ratio'], 2),
            "Entry Range": f"{round(entry * 0.99, 2)} - {round(entry * 1.005, 2)}",
            "Stop Loss":   round(entry - 1.0 * atr, 2),
            "Target":      round(entry + 1.5 * atr, 2),  # Refactored from 1.2 to 1.5
            "Risk_Reward": "1:1.50",
            "Reason":      "Oversold rebound from lower Bollinger Band — mean reversion play.",
        }

    return False, None


def screen_supertrend_reversal(df: pd.DataFrame):
    """
    Supertrend Reversal: Supertrend flips to bullish.
    """
    if df is None or len(df) < 5:
        return False, None

    r = df.iloc[-1]
    p = df.iloc[-2]

    crossed_up = p['ST_Direction'] == -1 and r['ST_Direction'] == 1
    trend_ok   = r['Close'] > r['EMA50']

    if crossed_up and trend_ok:
        atr = r['ATR']
        entry = r['Close']
        return True, {
            "Strategy":    "Supertrend Reversal",
            "Price":       round(entry, 2),
            "RSI":         round(r['RSI'], 1),
            "Vol_Ratio":   round(r['Vol_Ratio'], 2),
            "Entry Range": f"{round(entry * 0.995, 2)} - {round(entry * 1.005, 2)}",
            "Stop Loss":   round(entry - 1.5 * atr, 2),
            "Target":      round(entry + 2.0 * atr, 2),
            "Risk_Reward": "1:1.33",
            "Reason":      "Supertrend flipped to bullish in primary uptrend.",
        }

    return False, None


def screen_adx_trend_strength(df: pd.DataFrame):
    """
    ADX Trend Strength: Strong trend confirmation.
    """
    if df is None or len(df) < 5:
        return False, None

    r = df.iloc[-1]

    strong_trend = r['ADX'] > 25
    bullish      = r['PlusDI'] > r['MinusDI']
    above_ema20  = r['Close'] > r['EMA20']
    momentum_ok  = 45 <= r['RSI'] <= 65

    if strong_trend and bullish and above_ema20 and momentum_ok:
        atr = r['ATR']
        entry = r['Close']
        return True, {
            "Strategy":    "ADX Trend Strength",
            "Price":       round(entry, 2),
            "RSI":         round(r['RSI'], 1),
            "Vol_Ratio":   round(r['Vol_Ratio'], 2),
            "Entry Range": f"{round(entry * 0.995, 2)} - {round(entry * 1.005, 2)}",
            "Stop Loss":   round(entry - 1.5 * atr, 2),
            "Target":      round(entry + 2.0 * atr, 2),
            "Risk_Reward": "1:1.33",
            "Reason":      "Strong ADX momentum trend with solid moving average structure.",
        }

    return False, None


def screen_high_conviction_95pct(df: pd.DataFrame):
    """
    High-Conviction 95% Pullback: Designed for extreme success rate in strong trends.
    """
    if df is None or len(df) < 20:
        return False, None

    r = df.iloc[-1]
    p = df.iloc[-2]

    trend_ok = r['Close'] > r['EMA20'] and r['EMA20'] > r['EMA50'] > r['EMA200']
    pullback_ok = (r['Low'] <= r['EMA20'] * 1.01) or (35 <= r['RSI'] <= 48)
    candle_ok = r['Close'] >= r['Open'] or r['Close'] > p['Close']
    vol_ok = r['Vol_Ratio'] >= 1.1

    if trend_ok and pullback_ok and candle_ok and vol_ok:
        atr = r['ATR']
        entry = r['Close']
        return True, {
            "Strategy":    "High-Conviction 95% Pullback",
            "Price":       round(entry, 2),
            "RSI":         round(r['RSI'], 1),
            "Vol_Ratio":   round(r['Vol_Ratio'], 2),
            "Entry Range": f"{round(entry * 0.995, 2)} - {round(entry * 1.005, 2)}",
            "Stop Loss":   round(entry - 1.8 * atr, 2),  # Refactored from 2.2 to 1.8
            "Target":      round(entry + 1.2 * atr, 2),  # Refactored from 1.0 to 1.2
            "Risk_Reward": "1:0.67",
            "Reason":      "High-probability pullback setup aligned with long-term trend, backed by wide ATR stop.",
        }

    return False, None


# ---------------------------------------------------------------------------
# Screener Runners
# ---------------------------------------------------------------------------

_SHORT_STRATEGIES = {
    "EMA Pullback (20)":       screen_ema_pullback,
    "RSI Reversal & Pullback": screen_rsi_pullback,
    "Volume Breakout":         screen_volume_breakout,
    "MACD Crossover":          screen_macd_crossover,
    "Bollinger Rebound":       screen_bollinger_rebound,
    "Supertrend Reversal":     screen_supertrend_reversal,
    "ADX Trend Strength":      screen_adx_trend_strength,
    "High-Conviction 95% Pullback": screen_high_conviction_95pct,
}


def run_screener_on_data(ticker: str, df_history: pd.DataFrame, strategy_name: str) -> dict | None:
    """Runs a short-term strategy screener on pre-computed indicator dataframe."""
    df = calculate_indicators(df_history)
    if df is None:
        return None

    fns = list(_SHORT_STRATEGIES.values()) if strategy_name == "All Strategies" \
          else [_SHORT_STRATEGIES[strategy_name]] if strategy_name in _SHORT_STRATEGIES else []

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
    Fixed: no longer double-calls calculate_indicators.
    """
    df = calculate_indicators(df_history)
    if df is None or len(df) < 30:
        return []

    past_picks = []
    N = len(df)

    for idx in range(N - 6, N - 1):
        if idx < 20:
            continue

        slice_df = df.iloc[:idx + 1]   # Already has indicators — pass directly

        fns = list(_SHORT_STRATEGIES.values()) if strategy_name == "All Strategies" \
              else [_SHORT_STRATEGIES[strategy_name]] if strategy_name in _SHORT_STRATEGIES else []

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
