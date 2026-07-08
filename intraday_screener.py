"""
intraday_screener.py
Intraday Buy-Sell (Long) and Sell-Buy (Short) strategy check functions
and 10-day backtesting simulation.
"""
import pandas as pd
import numpy as np
import os
import json
import datetime
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
# 🟢 Buy-First (Long) Strategies
# ---------------------------------------------------------------------------

def check_vwap_bounce_long(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r = df.iloc[i]
    # Close > VWAP, Low touched VWAP (within 0.5%)
    cond1 = r['Close'] > r['VWAP']
    cond2 = r['Low'] <= r['VWAP'] * 1.005
    cond3 = r['Close'] >= r['Open']  # Green candle
    cond4 = r['RSI'] > 40
    cond5 = r['Vol_Ratio'] >= 1.2
    
    if cond1 and cond2 and cond3 and cond4 and cond5:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Strategy": "VWAP Bounce (Long)",
            "Price": round(entry, 2),
            "RSI": round(r['RSI'], 1),
            "Vol_Ratio": round(r['Vol_Ratio'], 2),
            "Entry Range": f"{round(entry * 0.995, 2)} - {round(entry * 1.005, 2)}",
            "Stop Loss": round(entry - 0.7 * atr, 2),
            "Target": round(entry + 1.0 * atr, 2),
            "Risk_Reward": "1:1.43",
            "Reason": "Bullish rebound from dynamic VWAP support under healthy volume.",
            "Type": "BUY-SELL"
        }
    return None

def check_orb_breakout_long(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r = df.iloc[i]
    p = df.iloc[i-1]
    # Close > previous day's High
    cond1 = r['Close'] > p['High']
    cond2 = r['Vol_Ratio'] >= 1.5
    cond3 = r['MACD_Hist'] > 0
    
    if cond1 and cond2 and cond3:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Strategy": "ORB Breakout (Long)",
            "Price": round(entry, 2),
            "RSI": round(r['RSI'], 1),
            "Vol_Ratio": round(r['Vol_Ratio'], 2),
            "Entry Range": f"{round(entry, 2)} - {round(entry * 1.01, 2)}",
            "Stop Loss": round(entry - 0.8 * atr, 2),
            "Target": round(entry + 1.2 * atr, 2),
            "Risk_Reward": "1:1.50",
            "Reason": "Momentum breakout past previous day's high confirmed by volume & MACD.",
            "Type": "BUY-SELL"
        }
    return None

def check_ema_crossover_long(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r = df.iloc[i]
    p = df.iloc[i-1]
    # EMA9 crosses above EMA21
    cond1 = p['EMA9'] <= p['EMA21'] and r['EMA9'] > r['EMA21']
    cond2 = r['Close'] > r['EMA50']
    cond3 = 45 <= r['RSI'] <= 70
    
    if cond1 and cond2 and cond3:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Strategy": "EMA 9/21 Crossover (Long)",
            "Price": round(entry, 2),
            "RSI": round(r['RSI'], 1),
            "Vol_Ratio": round(r['Vol_Ratio'], 2),
            "Entry Range": f"{round(entry * 0.995, 2)} - {round(entry * 1.005, 2)}",
            "Stop Loss": round(entry - 0.7 * atr, 2),
            "Target": round(entry + 1.0 * atr, 2),
            "Risk_Reward": "1:1.43",
            "Reason": "Bullish moving average crossover in primary uptrend.",
            "Type": "BUY-SELL"
        }
    return None

# ---------------------------------------------------------------------------
# 🔴 Sell-First (Short) Strategies
# ---------------------------------------------------------------------------

def check_vwap_rejection_short(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r = df.iloc[i]
    # Close < VWAP, High touched VWAP (within 0.5%)
    cond1 = r['Close'] < r['VWAP']
    cond2 = r['High'] >= r['VWAP'] * 0.995
    cond3 = r['Close'] < r['Open']  # Red candle
    cond4 = r['RSI'] < 55
    cond5 = r['Vol_Ratio'] >= 1.2
    
    if cond1 and cond2 and cond3 and cond4 and cond5:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Strategy": "VWAP Rejection (Short)",
            "Price": round(entry, 2),
            "RSI": round(r['RSI'], 1),
            "Vol_Ratio": round(r['Vol_Ratio'], 2),
            "Entry Range": f"{round(entry * 0.995, 2)} - {round(entry * 1.005, 2)}",
            "Stop Loss": round(entry + 0.7 * atr, 2),  # SL is above entry for short
            "Target": round(entry - 1.0 * atr, 2),     # Target is below entry for short
            "Risk_Reward": "1:1.43",
            "Reason": "Bearish rejection from dynamic VWAP resistance line.",
            "Type": "SELL-BUY"
        }
    return None

def check_gap_down_short(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r = df.iloc[i]
    p = df.iloc[i-1]
    # Open gap down >= 0.5%
    cond1 = r['Open'] < p['Close'] * 0.995
    cond2 = r['Close'] < r['Open']  # Red candle
    cond3 = r['Vol_Ratio'] >= 1.3
    
    if cond1 and cond2 and cond3:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Strategy": "Gap-Down Continuation (Short)",
            "Price": round(entry, 2),
            "RSI": round(r['RSI'], 1),
            "Vol_Ratio": round(r['Vol_Ratio'], 2),
            "Entry Range": f"{round(entry * 0.99, 2)} - {round(entry, 2)}",
            "Stop Loss": round(entry + 0.8 * atr, 2),
            "Target": round(entry - 1.2 * atr, 2),
            "Risk_Reward": "1:1.50",
            "Reason": "Sustained gap down with volume indicating strong institutional selling.",
            "Type": "SELL-BUY"
        }
    return None

def check_ema_crossover_short(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r = df.iloc[i]
    p = df.iloc[i-1]
    # EMA9 crosses below EMA21
    cond1 = p['EMA9'] >= p['EMA21'] and r['EMA9'] < r['EMA21']
    cond2 = r['Close'] < r['EMA50']
    cond3 = 30 <= r['RSI'] <= 55
    
    if cond1 and cond2 and cond3:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Strategy": "EMA 9/21 Crossover (Short)",
            "Price": round(entry, 2),
            "RSI": round(r['RSI'], 1),
            "Vol_Ratio": round(r['Vol_Ratio'], 2),
            "Entry Range": f"{round(entry * 0.995, 2)} - {round(entry * 1.005, 2)}",
            "Stop Loss": round(entry + 0.7 * atr, 2),
            "Target": round(entry - 1.0 * atr, 2),
            "Risk_Reward": "1:1.43",
            "Reason": "Bearish moving average crossover in primary downtrend.",
            "Type": "SELL-BUY"
        }
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
            
            if is_short:
                if day_high >= sl:
                    status = "Stop Loss Hit"
                    exit_price = sl
                    exit_idx = check_idx
                elif day_low <= target:
                    status = "Target Hit"
                    exit_price = target
                    exit_idx = check_idx
                else:
                    status = "Time Exit"
                    exit_price = day_close
                    exit_idx = check_idx
            else:
                if day_low <= sl:
                    status = "Stop Loss Hit"
                    exit_price = sl
                    exit_idx = check_idx
                elif day_high >= target:
                    status = "Target Hit"
                    exit_price = target
                    exit_idx = check_idx
                else:
                    status = "Time Exit"
                    exit_price = day_close
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
