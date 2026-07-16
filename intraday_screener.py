"""
intraday_screener.py
Intraday Buy-Sell (Long) and Sell-Buy (Short) strategy check functions
and 10-day backtesting simulation.
"""
import pandas as pd
import screeners as scr

def calculate_intraday_indicators(df: pd.DataFrame) -> pd.DataFrame | None:
    """Enriches daily EOD data with intraday-grade indicators (EMA 9, EMA 21)."""
    df_ind = scr.calculate_indicators(df)
    if df_ind is None:
        return None
    df_ind = df_ind.copy()
    close = df_ind['Close']
    df_ind['EMA9'] = close.ewm(span=9, adjust=False).mean()
    df_ind['EMA21'] = close.ewm(span=21, adjust=False).mean()
    return df_ind

# ---------------------------------------------------------------------------
# Shared signal builder
# ---------------------------------------------------------------------------

def _intra_signal(r, *, strategy: str, sl_mult: float, tgt_mult: float,
                  reason: str, is_short: bool,
                  entry_low: float = 0.995, entry_high: float = 1.005) -> dict:
    """Build a display-ready intraday signal with ATR-scaled stop/target.

    For shorts the stop sits *above* entry and the target *below* it; the
    reward:risk label is derived from the multipliers so it can never disagree
    with the printed levels.
    """
    atr = r['ATR']
    entry = r['Close']
    if is_short:
        stop, target, trade_type = entry + sl_mult * atr, entry - tgt_mult * atr, "SELL-BUY"
    else:
        stop, target, trade_type = entry - sl_mult * atr, entry + tgt_mult * atr, "BUY-SELL"
    return {
        "Strategy": strategy,
        "Price": round(entry, 2),
        "RSI": round(r['RSI'], 1),
        "Vol_Ratio": round(r['Vol_Ratio'], 2),
        "Entry Range": f"{round(entry * entry_low, 2)} - {round(entry * entry_high, 2)}",
        "Stop Loss": round(stop, 2),
        "Target": round(target, 2),
        "Risk_Reward": f"1:{tgt_mult / sl_mult:.2f}",
        "Reason": reason,
        "Type": trade_type,
    }


# ---------------------------------------------------------------------------
# 🟢 Buy-First (Long) Strategies
# ---------------------------------------------------------------------------

def check_vwap_bounce_long(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r = df.iloc[i]
    # Close reclaims VWAP after tagging it (within 0.5%) on a green, high-volume bar.
    if (r['Close'] > r['VWAP'] and r['Low'] <= r['VWAP'] * 1.005
            and r['Close'] >= r['Open'] and r['RSI'] > 40 and r['Vol_Ratio'] >= 1.2):
        return _intra_signal(
            r, strategy="VWAP Bounce (Long)", sl_mult=0.7, tgt_mult=1.0, is_short=False,
            reason="Bullish rebound from dynamic VWAP support under healthy volume.",
        )
    return None


def check_orb_breakout_long(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r, p = df.iloc[i], df.iloc[i - 1]
    # Close breaks the previous bar's high with volume and positive MACD momentum.
    if r['Close'] > p['High'] and r['Vol_Ratio'] >= 1.5 and r['MACD_Hist'] > 0:
        return _intra_signal(
            r, strategy="ORB Breakout (Long)", sl_mult=0.8, tgt_mult=1.2, is_short=False,
            entry_low=1.0, entry_high=1.01,
            reason="Momentum breakout past previous day's high confirmed by volume & MACD.",
        )
    return None


def check_ema_crossover_long(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r, p = df.iloc[i], df.iloc[i - 1]
    # EMA9 crosses above EMA21 while price holds above EMA50.
    if (p['EMA9'] <= p['EMA21'] and r['EMA9'] > r['EMA21']
            and r['Close'] > r['EMA50'] and 45 <= r['RSI'] <= 70):
        return _intra_signal(
            r, strategy="EMA 9/21 Crossover (Long)", sl_mult=0.7, tgt_mult=1.0, is_short=False,
            reason="Bullish moving average crossover in primary uptrend.",
        )
    return None


# ---------------------------------------------------------------------------
# 🔴 Sell-First (Short) Strategies
# ---------------------------------------------------------------------------

def check_vwap_rejection_short(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r = df.iloc[i]
    # Close fails at VWAP after tagging it from below on a red, high-volume bar.
    if (r['Close'] < r['VWAP'] and r['High'] >= r['VWAP'] * 0.995
            and r['Close'] < r['Open'] and r['RSI'] < 55 and r['Vol_Ratio'] >= 1.2):
        return _intra_signal(
            r, strategy="VWAP Rejection (Short)", sl_mult=0.7, tgt_mult=1.0, is_short=True,
            reason="Bearish rejection from dynamic VWAP resistance line.",
        )
    return None


def check_gap_down_short(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r, p = df.iloc[i], df.iloc[i - 1]
    # Gap down >= 0.5% that keeps selling into the close on elevated volume.
    if r['Open'] < p['Close'] * 0.995 and r['Close'] < r['Open'] and r['Vol_Ratio'] >= 1.3:
        return _intra_signal(
            r, strategy="Gap-Down Continuation (Short)", sl_mult=0.8, tgt_mult=1.2, is_short=True,
            entry_low=0.99, entry_high=1.0,
            reason="Sustained gap down with volume indicating strong institutional selling.",
        )
    return None


def check_ema_crossover_short(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r, p = df.iloc[i], df.iloc[i - 1]
    # EMA9 crosses below EMA21 while price stays under EMA50.
    if (p['EMA9'] >= p['EMA21'] and r['EMA9'] < r['EMA21']
            and r['Close'] < r['EMA50'] and 30 <= r['RSI'] <= 55):
        return _intra_signal(
            r, strategy="EMA 9/21 Crossover (Short)", sl_mult=0.7, tgt_mult=1.0, is_short=True,
            reason="Bearish moving average crossover in primary downtrend.",
        )
    return None


# ---------------------------------------------------------------------------
# Screener Registries & Runner
# ---------------------------------------------------------------------------

INTRADAY_STRATEGIES = {
    "VWAP Bounce (Long)": check_vwap_bounce_long,
    "ORB Breakout (Long)": check_orb_breakout_long,
    "EMA 9/21 Crossover (Long)": check_ema_crossover_long,
    "VWAP Rejection (Short)": check_vwap_rejection_short,
    "Gap-Down Continuation (Short)": check_gap_down_short,
    "EMA 9/21 Crossover (Short)": check_ema_crossover_short,
}

def run_intraday_screener(ticker: str, df_history: pd.DataFrame) -> list:
    """Scans the latest day's data for any matching intraday signals."""
    df = calculate_intraday_indicators(df_history)
    if df is None or len(df) < 50:
        return []
        
    results = []
    i = len(df) - 1
    for name, fn in INTRADAY_STRATEGIES.items():
        res = fn(df, i)
        if res:
            res["Ticker"] = ticker
            results.append(res)
    return results

# ---------------------------------------------------------------------------
# 10-Day Intraday Backtesting
# ---------------------------------------------------------------------------

def _evaluate_exit(
    day_high: float,
    day_low: float,
    day_close: float,
    sl: float,
    target: float,
    is_short: bool,
) -> tuple[str, float]:
    """Return (status, exit_price) for one intraday bar given SL/target levels.

    For long trades (``is_short=False``) the stop-loss sits *below* entry and
    the target *above*.  For short trades the directions are reversed.
    Stop-loss takes priority over target (conservative simulation).
    """
    if is_short:
        if day_high >= sl:
            return "Stop Loss Hit", sl
        if day_low <= target:
            return "Target Hit", target
    else:
        if day_low <= sl:
            return "Stop Loss Hit", sl
        if day_high >= target:
            return "Target Hit", target
    return "Time Exit", day_close

def backtest_intraday_10days(ticker: str, df_history: pd.DataFrame) -> list:
    """
    Simulates intraday trades triggered over the last 10 trading days.
    Intraday exit logic: hold max 1 trading day (exit at next day's close if target/SL not hit).
    Handles short-selling trade logic correctly (SL above entry, Target below entry).
    """
    df = calculate_intraday_indicators(df_history)
    if df is None or len(df) < 30:
        return []
        
    N = len(df)
    # Scan trigger window: past 10 trading days up to N-1
    start_idx = max(20, N - 11)
    end_idx = N - 1
    
    trades = []
    
    for idx in range(start_idx, end_idx + 1):
        for name, fn in INTRADAY_STRATEGIES.items():
            res = fn(df, idx)
            if not res:
                continue
                
            trigger_date = df.index[idx]
            entry_price = res["Price"]
            target = res["Target"]
            sl = res["Stop Loss"]
            is_short = res.get("Type") == "SELL-BUY"
            
            # Simulate a 1-day hold (exit by next day's close)
            exit_idx = idx
            status = "Active"
            exit_price = entry_price
            
            check_idx = idx + 1 if idx + 1 < N else idx
            day_high = df['High'].iloc[check_idx]
            day_low = df['Low'].iloc[check_idx]
            day_close = df['Close'].iloc[check_idx]

            status, exit_price = _evaluate_exit(day_high, day_low, day_close, sl, target, is_short)
            exit_idx = check_idx
                    
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            if is_short:
                pnl_pct = ((entry_price - exit_price) / entry_price) * 100
                
            trades.append({
                "Ticker": ticker.replace(".NS", ""),
                "Trigger Date": trigger_date.strftime("%Y-%m-%d"),
                "Strategy": name,
                "Type": "SELL-BUY" if is_short else "BUY-SELL",
                "Entry Price": round(entry_price, 2),
                "Target": round(target, 2),
                "Stop Loss": round(sl, 2),
                "Current/Exit": round(exit_price, 2),
                "P&L (%)": round(pnl_pct, 2),
                "Status": status,
                "Days Held": exit_idx - idx
            })
            
    return trades
