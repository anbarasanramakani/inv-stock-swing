"""
optimizer.py
Backtesting and optimization engine for multi-strategy evaluation.

Evaluates every individual strategy defined in ``strategies.py`` plus their
pairwise AND / OR combinations and 2/3/4-of-N consensus models over a rolling
backtest window. Entry conditions and ATR stop/target multipliers are imported
from ``strategies.py`` so this engine can never drift from the live screeners.
"""
import json
import os
import datetime
import itertools

import numpy as np
import pandas as pd

import screeners as scr
import strategies as strat


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that understands numpy scalars and pandas/py datetimes."""

    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (pd.Timestamp, datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)


# ---------------------------------------------------------------------------
# Individual strategy checkers — derived from the shared spec registry.
# Each returns {"Price", "Target", "Stop Loss", "Strategy"} or None at index i.
# ---------------------------------------------------------------------------

def _make_check(spec):
    return lambda df, i: strat.price_targets(spec, df, i)

CHECK_FUNCTIONS = {spec.name: _make_check(spec) for spec in strat.SPECS}


# ---------------------------------------------------------------------------
# Backtest Engine
# ---------------------------------------------------------------------------

def run_3month_optimization(df_raw: pd.DataFrame, hold_days: int = 5, backtest_days: int = 60, ticker: str = "") -> tuple[pd.DataFrame, dict]:
    """
    Runs multi-strategy backtesting on a stock's daily OHLCV data.
    Evaluates individual strategies and mixed strategies.
    Supports cache lookup based on ticker, hold_days, and backtest_days.
    """
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
        
    # 2. Build the strategy grid: N individual + every AND/OR pair + consensus
    strategy_definitions = []
    
    # Individual strategies
    for name in CHECK_FUNCTIONS.keys():
        strategy_definitions.append({"name": name, "type": "individual", "sub_strats": [name]})
        
    # AND pairs
    individual_names = list(CHECK_FUNCTIONS.keys())
    for s1, s2 in itertools.combinations(individual_names, 2):
        strategy_definitions.append({
            "name": f"{s1} AND {s2}",
            "type": "and",
            "sub_strats": [s1, s2]
        })
        
    # OR pairs
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
    
    for strat_def in strategy_definitions:
        strat_name = strat_def["name"]
        strat_type = strat_def["type"]
        trades = []
        
        for idx in range(start_idx, end_idx + 1):
            triggered = False
            trigger_details = []
            
            # Check trigger condition
            day_sigs = day_signals.get(idx, {})
            
            if strat_type == "individual":
                target_strat = strat_def["sub_strats"][0]
                if target_strat in day_sigs:
                    triggered = True
                    trigger_details.append(day_sigs[target_strat])
            
            elif strat_type == "and":
                s1, s2 = strat_def["sub_strats"]
                if s1 in day_sigs and s2 in day_sigs:
                    triggered = True
                    trigger_details.append(day_sigs[s1])
                    trigger_details.append(day_sigs[s2])
                    
            elif strat_type == "or":
                s1, s2 = strat_def["sub_strats"]
                if s1 in day_sigs:
                    trigger_details.append(day_sigs[s1])
                if s2 in day_sigs:
                    trigger_details.append(day_sigs[s2])
                triggered = len(trigger_details) > 0
                
            elif strat_type == "consensus":
                threshold = strat_def["threshold"]
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
