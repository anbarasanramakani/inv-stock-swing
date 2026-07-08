"""
optimizer.py
Backtesting and optimization engine for multi-strategy evaluation.
Tests 6 individual strategies and 33 mixed combinations (AND, OR, Consensus) over 3 months.
"""
import pandas as pd
import numpy as np
import itertools
import screeners as scr

# ---------------------------------------------------------------------------
# Individual Strategy Checkers (Fast, index-based)
# ---------------------------------------------------------------------------

def check_ema_pullback(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r = df.iloc[i]
    p = df.iloc[i-1]
    
    trend_ok = r['Close'] > r['EMA50'] > r['EMA200']
    pullback_ok = (r['Low'] <= r['EMA20'] * 1.01) and (r['Close'] >= r['EMA20'] * 0.99)
    candle_ok = r['Close'] >= r['Open'] or r['Close'] > p['Close']
    
    if trend_ok and pullback_ok and candle_ok:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Price": entry,
            "Target": entry + 2.0 * atr,  # Refactored from 1.5 to 2.0
            "Stop Loss": entry - 1.5 * atr,  # Refactored from 1.0 to 1.5
            "Strategy": "EMA Pullback (20)"
        }
    return None

def check_rsi_reversal(df: pd.DataFrame, i: int) -> dict | None:
    if i < 2:
        return None
    r = df.iloc[i]
    recent_rsi = df['RSI'].iloc[i-2:i+1].tolist()
    
    # RSI crossed above 30 in the last 3 bars + trend filter (Close > EMA200)
    if recent_rsi[-1] > 30 and any(v < 30 for v in recent_rsi[:-1]) and r['Close'] > r['EMA200']:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Price": entry,
            "Target": entry + 1.8 * atr,  # Refactored from 1.2 to 1.8
            "Stop Loss": entry - 1.0 * atr,
            "Strategy": "RSI Reversal (Oversold)"
        }
    return None

def check_rsi_pullback(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r = df.iloc[i]
    p = df.iloc[i-1]
    
    trend_ok = r['Close'] > r['EMA50']
    rsi_pullback = 38 <= r['RSI'] <= 55 and r['RSI'] > p['RSI']  # Refactored range
    green_candle = r['Close'] > r['Open']
    vol_ok = r['Vol_Ratio'] >= 1.1  # Added volume confirmation
    
    if trend_ok and rsi_pullback and green_candle and vol_ok:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Price": entry,
            "Target": entry + 1.5 * atr,
            "Stop Loss": entry - 1.0 * atr,
            "Strategy": "RSI Pullback (Uptrend)"
        }
    return None

def check_volume_breakout(df: pd.DataFrame, i: int) -> dict | None:
    if i < 20:
        return None
    r = df.iloc[i]
    price_high20 = df['Close'].iloc[i-20:i].max()
    price_breakout = r['Close'] > price_high20
    volume_spike = r['Vol_Ratio'] >= 2.0  # Refactored from 1.8 to 2.0
    above_ema20 = r['Close'] > r['EMA20']  # Added above EMA20 filter
    
    if price_breakout and volume_spike and above_ema20:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Price": entry,
            "Target": entry + 1.5 * atr,
            "Stop Loss": entry - 1.0 * atr,
            "Strategy": "Volume Breakout"
        }
    return None

def check_macd_crossover(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r = df.iloc[i]
    p = df.iloc[i-1]
    
    crossed_above = p['MACD_Hist'] <= 0 < r['MACD_Hist']
    near_zero = abs(r['MACD']) < abs(r['Close']) * 0.03
    not_overbought = r['RSI'] < 65  # Added RSI filter
    
    if crossed_above and near_zero and not_overbought:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Price": entry,
            "Target": entry + 1.5 * atr,  # Refactored from 1.2 to 1.5
            "Stop Loss": entry - 1.0 * atr,
            "Strategy": "MACD Crossover"
        }
    return None

def check_bollinger_rebound(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r = df.iloc[i]
    p = df.iloc[i-1]
    
    touched_lower = (p['Low'] <= p['BB_Lower']) or (r['Low'] <= r['BB_Lower'])
    closed_inside = r['Close'] > r['BB_Lower']
    green_candle = r['Close'] > r['Open']
    trend_ok = r['Close'] > r['EMA50']  # Added trend filter
    
    if touched_lower and closed_inside and green_candle and trend_ok:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Price": entry,
            "Target": entry + 1.5 * atr,  # Refactored from 1.2 to 1.5
            "Stop Loss": entry - 1.0 * atr,
            "Strategy": "Bollinger Rebound"
        }
    return None

def check_supertrend_reversal(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r = df.iloc[i]
    p = df.iloc[i-1]
    
    crossed_up = p['ST_Direction'] == -1 and r['ST_Direction'] == 1
    trend_ok = r['Close'] > r['EMA50']
    
    if crossed_up and trend_ok:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Price": entry,
            "Target": entry + 2.0 * atr,
            "Stop Loss": entry - 1.5 * atr,
            "Strategy": "Supertrend Reversal"
        }
    return None

def check_adx_trend_strength(df: pd.DataFrame, i: int) -> dict | None:
    if i < 1:
        return None
    r = df.iloc[i]
    
    strong_trend = r['ADX'] > 25
    bullish = r['PlusDI'] > r['MinusDI']
    above_ema20 = r['Close'] > r['EMA20']
    momentum_ok = 45 <= r['RSI'] <= 65
    
    if strong_trend and bullish and above_ema20 and momentum_ok:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Price": entry,
            "Target": entry + 2.0 * atr,
            "Stop Loss": entry - 1.5 * atr,
            "Strategy": "ADX Trend Strength"
        }
    return None

def check_high_conviction_95pct(df: pd.DataFrame, i: int) -> dict | None:
    if i < 20:
        return None
    r = df.iloc[i]
    p = df.iloc[i-1]
    
    trend_ok = r['Close'] > r['EMA20'] and r['EMA20'] > r['EMA50'] > r['EMA200']
    pullback_ok = (r['Low'] <= r['EMA20'] * 1.01) or (35 <= r['RSI'] <= 48)
    candle_ok = r['Close'] >= r['Open'] or r['Close'] > p['Close']
    vol_ok = r['Vol_Ratio'] >= 1.1
    
    if trend_ok and pullback_ok and candle_ok and vol_ok:
        atr = r['ATR']
        entry = r['Close']
        return {
            "Price": entry,
            "Target": entry + 1.2 * atr,  # Refactored from 1.0 to 1.2
            "Stop Loss": entry - 1.8 * atr,  # Refactored from 2.2 to 1.8
            "Strategy": "High-Conviction 95% Pullback"
        }
    return None

# Mapping of individual strategies
CHECK_FUNCTIONS = {
    "EMA Pullback (20)": check_ema_pullback,
    "RSI Reversal (Oversold)": check_rsi_reversal,
    "RSI Pullback (Uptrend)": check_rsi_pullback,
    "Volume Breakout": check_volume_breakout,
    "MACD Crossover": check_macd_crossover,
    "Bollinger Rebound": check_bollinger_rebound,
    "Supertrend Reversal": check_supertrend_reversal,
    "ADX Trend Strength": check_adx_trend_strength,
    "High-Conviction 95% Pullback": check_high_conviction_95pct,
}

# ---------------------------------------------------------------------------
# Backtest Engine
# ---------------------------------------------------------------------------

def run_3month_optimization(df_raw: pd.DataFrame, hold_days: int = 5, backtest_days: int = 60, ticker: str = "") -> tuple[pd.DataFrame, dict]:
    """
    Runs multi-strategy backtesting on a stock's daily OHLCV data.
    Evaluates individual strategies and mixed strategies.
    Supports cache lookup based on ticker, hold_days, and backtest_days.
    """
    import json
    import os
    import datetime
    
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (np.int64, np.int32, np.integer)):
                return int(obj)
            elif isinstance(obj, (np.float64, np.float32, np.floating)):
                return float(obj)
            elif isinstance(obj, (pd.Timestamp, datetime.date, datetime.datetime)):
                return obj.isoformat()
            return super().default(obj)

    # 1. Cache lookup
    cache_path = None
    if ticker:
        clean_ticker = ticker.replace(".NS", "").replace("^", "_").strip().upper()
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"bt_{clean_ticker}_{hold_days}_{backtest_days}.json")
        
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                expected_len = len(df_raw)
                expected_date = df_raw.index[-1].strftime("%Y-%m-%d") if not df_raw.empty else ""
                if cache_data.get("df_len") == expected_len and cache_data.get("last_date") == expected_date:
                    sum_df = pd.DataFrame(cache_data["summary_records"])
                    trade_logs = cache_data["trade_logs"]
                    return sum_df, trade_logs
            except Exception as e:
                print(f"Error reading backtest cache for {ticker}: {e}")

    df = scr.calculate_indicators(df_raw)
    if df is None or len(df) < 50:
        return pd.DataFrame(), {}
        
    N = len(df)
    # Define trigger scanning window: last 60 trading days (approx 3 months) up to N-1
    start_idx = max(20, N - backtest_days)
    end_idx = N - 1
    
    # 1. Gather individual triggers for each day in the scanning window
    day_signals = {}  # index -> dict of {strategy_name: signal_dict}
    for idx in range(start_idx, end_idx + 1):
        signals = {}
        for name, fn in CHECK_FUNCTIONS.items():
            res = fn(df, idx)
            if res:
                signals[name] = res
        day_signals[idx] = signals
        
    # 2. Define all 39 strategies to backtest
    strategy_definitions = []
    
    # Six individual strategies
    for name in CHECK_FUNCTIONS.keys():
        strategy_definitions.append({"name": name, "type": "individual", "sub_strats": [name]})
        
    # 15 AND pairs
    individual_names = list(CHECK_FUNCTIONS.keys())
    for s1, s2 in itertools.combinations(individual_names, 2):
        strategy_definitions.append({
            "name": f"{s1} AND {s2}",
            "type": "and",
            "sub_strats": [s1, s2]
        })
        
    # 15 OR pairs
    for s1, s2 in itertools.combinations(individual_names, 2):
        strategy_definitions.append({
            "name": f"{s1} OR {s2}",
            "type": "or",
            "sub_strats": [s1, s2]
        })
        
    # 3 Consensus strategies
    strategy_definitions.append({"name": "Consensus (At least 2)", "type": "consensus", "threshold": 2})
    strategy_definitions.append({"name": "Consensus (At least 3)", "type": "consensus", "threshold": 3})
    strategy_definitions.append({"name": "Consensus (At least 4)", "type": "consensus", "threshold": 4})
    
    # 3. Simulate trades for each strategy definition
    summary_records = []
    trade_logs = {}
    
    for strat in strategy_definitions:
        strat_name = strat["name"]
        strat_type = strat["type"]
        trades = []
        
        for idx in range(start_idx, end_idx + 1):
            triggered = False
            trigger_details = []
            
            # Check trigger condition
            day_sigs = day_signals.get(idx, {})
            
            if strat_type == "individual":
                target_strat = strat["sub_strats"][0]
                if target_strat in day_sigs:
                    triggered = True
                    trigger_details.append(day_sigs[target_strat])
            
            elif strat_type == "and":
                s1, s2 = strat["sub_strats"]
                if s1 in day_sigs and s2 in day_sigs:
                    triggered = True
                    trigger_details.append(day_sigs[s1])
                    trigger_details.append(day_sigs[s2])
                    
            elif strat_type == "or":
                s1, s2 = strat["sub_strats"]
                if s1 in day_sigs:
                    trigger_details.append(day_sigs[s1])
                if s2 in day_sigs:
                    trigger_details.append(day_sigs[s2])
                triggered = len(trigger_details) > 0
                
            elif strat_type == "consensus":
                threshold = strat["threshold"]
                active_sigs = list(day_sigs.values())
                if len(active_sigs) >= threshold:
                    triggered = True
                    trigger_details = active_sigs
                    
            if not triggered:
                continue
                
            # If triggered, compute entry, target, stop loss
            entry_price = df['Close'].iloc[idx]
            # Average the targets of the triggering sub-strategies
            target = np.mean([t["Target"] for t in trigger_details])
            sl = np.mean([t["Stop Loss"] for t in trigger_details])
            
            # Track outcome forward in time
            status = "Active"
            days_held = 0
            exit_price = entry_price
            exit_idx = idx
            
            for check_idx in range(idx + 1, min(idx + hold_days + 1, N)):
                days_held += 1
                day_high = df['High'].iloc[check_idx]
                day_low = df['Low'].iloc[check_idx]
                
                # Check Stop Loss first (conservative)
                if day_low <= sl:
                    status = "Stop Loss Hit"
                    exit_price = sl
                    exit_idx = check_idx
                    break
                elif day_high >= target:
                    status = "Target Hit"
                    exit_price = target
                    exit_idx = check_idx
                    break
                    
            # Time exit if still active at the end of hold period
            if status == "Active":
                exit_idx = min(idx + hold_days, N - 1)
                days_held = exit_idx - idx
                exit_price = df['Close'].iloc[exit_idx]
                
                # Check if it was hit on the final day's low/high
                day_high = df['High'].iloc[exit_idx]
                day_low = df['Low'].iloc[exit_idx]
                if day_low <= sl:
                    status = "Stop Loss Hit"
                    exit_price = sl
                elif day_high >= target:
                    status = "Target Hit"
                    exit_price = target
                else:
                    status = "Time Exit"
                    
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            trigger_date = df.index[idx]
            exit_date = df.index[exit_idx]
            
            trades.append({
                "Trigger Date": trigger_date.strftime("%Y-%m-%d"),
                "Exit Date": exit_date.strftime("%Y-%m-%d"),
                "Entry Price": round(entry_price, 2),
                "Target": round(target, 2),
                "Stop Loss": round(sl, 2),
                "Exit Price": round(exit_price, 2),
                "P&L (%)": round(pnl_pct, 2),
                "Status": status,
                "Days Held": days_held
            })
            
        trade_logs[strat_name] = trades
        
        # Calculate summary statistics
        total_trades = len(trades)
        if total_trades > 0:
            target_hits = sum(1 for t in trades if t["Status"] == "Target Hit")
            sl_hits = sum(1 for t in trades if t["Status"] == "Stop Loss Hit")
            time_exits = sum(1 for t in trades if t["Status"] == "Time Exit")
            
            # Target Hit Rate is Target Hits / Total Trades (since they want 95% target hit rate)
            win_rate = (target_hits / total_trades) * 100
            avg_pnl = np.mean([t["P&L (%)"] for t in trades])
        else:
            target_hits = 0
            sl_hits = 0
            time_exits = 0
            win_rate = 0.0
            avg_pnl = 0.0
            
        summary_records.append({
            "Strategy": strat_name,
            "Type": strat_type.upper(),
            "Total Trades": total_trades,
            "Target Hits": target_hits,
            "Stop Loss Hits": sl_hits,
            "Time Exits": time_exits,
            "Target Hit Rate (%)": round(win_rate, 2),
            "Avg P&L (%)": round(avg_pnl, 2)
        })
        
    summary_df = pd.DataFrame(summary_records)
    if not summary_df.empty:
        # Sort by Target Hit Rate descending, then Total Trades descending, then Avg PnL descending
        summary_df = summary_df.sort_values(
            by=["Target Hit Rate (%)", "Total Trades", "Avg P&L (%)"],
            ascending=[False, False, False]
        ).reset_index(drop=True)
        
    if cache_path:
        try:
            cache_payload = {
                "df_len": len(df_raw),
                "last_date": df_raw.index[-1].strftime("%Y-%m-%d") if not df_raw.empty else "",
                "summary_records": summary_df.to_dict(orient="records"),
                "trade_logs": trade_logs
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_payload, f, cls=NumpyEncoder, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving backtest cache for {ticker}: {e}")
            
    return summary_df, trade_logs
