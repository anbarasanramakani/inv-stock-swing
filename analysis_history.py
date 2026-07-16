"""
analysis_history.py
Persistent analysis history tracking with target/SL validation across runs.
Supports incremental analysis: skips already-analyzed stocks, validates past picks.
"""
import json
import os
import datetime
import time
import pandas as pd
from typing import List


from pathlib import Path

HISTORY_CACHE_FILE = str(Path(__file__).parent / "analysis_history_cache.json")


# ---------------------------------------------------------------------------
# History Cache Schema
# ---------------------------------------------------------------------------
# {
#   "last_run_date": "2026-07-14",
#   "last_run_timestamp": 1234567890.0,
#   "runs": [
#     {
#       "run_id": "2026-07-14_123456",
#       "date": "2026-07-14",
#       "timestamp": 1234567890.0,
#       "universe": "Nifty 1000",
#       "strategy": "All Strategies",
#       "mode": "full",
#       "picks": [
#         {
#           "Ticker": "TCS.NS",
#           "Symbol": "TCS.NS",
#           "Strategy": "EMA Pullback (20)",
#           "Price": 2069.0,
#           "Entry Range": "2058.66 - 2079.34",
#           "Stop Loss": 1996.81,
#           "Target": 2159.24,
#           "Type": "BUY",
#           "Source": "swing",    # swing / medium / intraday / news
#           "Entry Date": "2026-07-14",
#           "Validation Window": 5,  # trading days to validate
#           "Status": "Active",   # Active / Target Met / Stop Loss Hit / Expired
#           "Exit Price": None,
#           "P&L (%)": None,
#           "Exit Date": None,
#         }
#       ]
#     }
#   ],
#   "broker_history": [
#     {
#       "Broker": "Motilal Oswal",
#       "Ticker": "TCS.NS",
#       "Action": "Buy",
#       "Target": 2300.0,
#       "Entry Date": "2026-07-01",
#       "Status": "Active",
#       "Current Price": 2069.0,
#       "P&L (%)": None,
#     }
#   ],
#   "broker_stats": {
#     "Motilal Oswal": {"total": 10, "success": 7, "win_rate": 70.0},
#     ...
#   }
# }


def _get_default_cache() -> dict:
    return {
        "last_run_date": "",
        "last_run_timestamp": 0.0,
        "runs": [],
        "broker_history": [],
        "broker_stats": {},
    }


def load_history_cache() -> dict:
    """Load the analysis history cache from disk."""
    if os.path.exists(HISTORY_CACHE_FILE):
        try:
            with open(HISTORY_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Ensure all keys exist
            default = _get_default_cache()
            for k, v in default.items():
                if k not in data:
                    data[k] = v
            return data
        except Exception as e:
            print(f"Error loading history cache: {e}")
    return _get_default_cache()


def save_history_cache(cache: dict):
    """Save the analysis history cache to disk."""
    try:
        with open(HISTORY_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        print(f"Error saving history cache: {e}")


def clear_history_cache():
    """Delete all history caches (fresh start)."""
    for f in [HISTORY_CACHE_FILE, "news_cache.json", "brokers_cache.json"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception as e:
                print(f"Error removing {f}: {e}")
    # Also delete .csv cache files
    for f in ["opt_backtest_cache.csv", "t1_backtest_cache.csv", "long_term_backtest_cache.csv"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception as e:
                print(f"Error removing {f}: {e}")


def _get_validation_window(strategy: str, source: str = "swing") -> int:
    """Determine the validation window in trading days."""
    if source == "medium":
        return 30  # medium-term: 15-30 days
    elif source == "intraday":
        return 2   # intraday: 1-2 days
    else:
        return 5   # short swing: 1-5 days


def add_run_to_history(
    cache: dict,
    date_str: str,
    universe: str,
    strategy: str,
    mode: str,
    pick_list: List[dict],
) -> dict:
    """Add a new analysis run to history and validate previous picks."""
    # First: validate all previous active picks against current data
    validate_previous_picks(cache, pick_list)

    # Then: add today's run
    run_id = f"{date_str}_{int(time.time())}"
    run_entry = {
        "run_id": run_id,
        "date": date_str,
        "timestamp": time.time(),
        "universe": universe,
        "strategy": strategy,
        "mode": mode,
        "picks": [],
    }

    for pick in pick_list:
        ticker = pick.get("Ticker") or pick.get("Symbol") or ""
        if not ticker:
            continue

        source = pick.get("Source", "swing")
        if "medium" in str(pick.get("Strategy", "")).lower():
            source = "medium"
        elif "intra" in str(pick.get("Strategy", "")).lower():
            source = "intraday"

        validation_window = _get_validation_window(
            pick.get("Strategy", ""), source
        )

        entry = dict(pick)
        entry.update({
            "Ticker": ticker,
            "Symbol": ticker.replace(".NS", ""),
            "Strategy": pick.get("Strategy", ""),
            "Price": pick.get("Price"),
            "Entry Range": pick.get("Entry Range", ""),
            "Stop Loss": pick.get("Stop Loss"),
            "Target": pick.get("Target"),
            "Type": pick.get("Type", "BUY"),
            "Source": source,
            "Entry Date": date_str,
            "Validation Window": validation_window,
            "Status": "Active",
            "Exit Price": None,
            "P&L (%)": None,
            "Exit Date": None,
        })
        run_entry["picks"].append(entry)

    cache["runs"].insert(0, run_entry)
    cache["last_run_date"] = date_str
    cache["last_run_timestamp"] = time.time()

    # Prune old runs (keep last 60 days)
    cutoff_ts = time.time() - (60 * 24 * 3600)
    cache["runs"] = [r for r in cache["runs"] if r.get("timestamp", 0) > cutoff_ts]

    save_history_cache(cache)
    return cache


def validate_previous_picks(cache: dict, current_picks: List[dict] = None):
    """
    Validate all active picks from previous runs against current price data.
    Uses current_picks list (from data_cache) to get latest prices.
    """
    if not cache.get("runs"):
        return

    # Build a lookup of current prices from current_picks
    current_price_map = {}
    if current_picks:
        for p in current_picks:
            ticker = p.get("Ticker") or p.get("Symbol") or ""
            price = p.get("Price")
            if ticker and price:
                current_price_map[ticker] = float(price)

    updated_count = 0
    for run in cache["runs"]:
        for pick in run.get("picks", []):
            if pick.get("Status") != "Active":
                continue

            ticker = pick.get("Ticker", "")
            price = pick.get("Price")
            sl = pick.get("Stop Loss")
            target = pick.get("Target")
            trade_type = pick.get("Type", "BUY")

            if price is None or sl is None or target is None:
                continue

            try:
                price = float(price)
                sl = float(sl)
                target = float(target)
            except (ValueError, TypeError):
                continue

            # Get current price from the latest data
            current_price = current_price_map.get(ticker)
            if current_price is None:
                continue

            days_since_entry = 0
            entry_date_str = pick.get("Entry Date", "")
            if entry_date_str:
                try:
                    entry_dt = datetime.datetime.strptime(entry_date_str, "%Y-%m-%d")
                    days_since_entry = (datetime.date.today() - entry_dt.date()).days
                except Exception:
                    pass

            validation_window = pick.get("Validation Window", 5)

            if trade_type == "SELL-BUY":
                # Short trade
                if current_price >= sl:
                    pick["Status"] = "Stop Loss Hit"
                    pick["Exit Price"] = round(current_price, 2)
                    pick["P&L (%)"] = round(((price - current_price) / price) * 100, 2)
                    pick["Exit Date"] = datetime.date.today().isoformat()
                    updated_count += 1
                elif current_price <= target:
                    pick["Status"] = "Target Met"
                    pick["Exit Price"] = round(current_price, 2)
                    pick["P&L (%)"] = round(((price - current_price) / price) * 100, 2)
                    pick["Exit Date"] = datetime.date.today().isoformat()
                    updated_count += 1
                elif days_since_entry > validation_window * 2:
                    pick["Status"] = "Expired"
                    pick["Exit Price"] = round(current_price, 2)
                    pick["P&L (%)"] = round(((price - current_price) / price) * 100, 2)
                    pick["Exit Date"] = datetime.date.today().isoformat()
                    updated_count += 1
            else:
                # Long trade
                if current_price <= sl:
                    pick["Status"] = "Stop Loss Hit"
                    pick["Exit Price"] = sl
                    pick["P&L (%)"] = round(((sl - price) / price) * 100, 2)
                    pick["Exit Date"] = datetime.date.today().isoformat()
                    updated_count += 1
                elif current_price >= target:
                    pick["Status"] = "Target Met"
                    pick["Exit Price"] = target
                    pick["P&L (%)"] = round(((target - price) / price) * 100, 2)
                    pick["Exit Date"] = datetime.date.today().isoformat()
                    updated_count += 1
                elif days_since_entry > validation_window * 2:
                    pick["Status"] = "Expired"
                    pick["Exit Price"] = round(current_price, 2)
                    pick["P&L (%)"] = round(((current_price - price) / price) * 100, 2)
                    pick["Exit Date"] = datetime.date.today().isoformat()
                    updated_count += 1

    if updated_count > 0:
        save_history_cache(cache)


def get_history_stats(cache: dict) -> dict:
    """Compute aggregate statistics from history."""
    total_picks = 0
    target_met = 0
    stop_loss_hit = 0
    expired = 0
    active = 0
    total_pnl = 0.0
    pnl_count = 0

    for run in cache.get("runs", []):
        for pick in run.get("picks", []):
            total_picks += 1
            status = pick.get("Status", "Active")
            if status == "Target Met":
                target_met += 1
            elif status == "Stop Loss Hit":
                stop_loss_hit += 1
            elif status == "Expired":
                expired += 1
            else:
                active += 1

            pnl = pick.get("P&L (%)")
            if pnl is not None:
                total_pnl += pnl
                pnl_count += 1

    decided = target_met + stop_loss_hit
    win_rate = (target_met / decided * 100) if decided > 0 else 0.0
    avg_pnl = (total_pnl / pnl_count) if pnl_count > 0 else 0.0

    return {
        "total_picks": total_picks,
        "target_met": target_met,
        "stop_loss_hit": stop_loss_hit,
        "expired": expired,
        "active": active,
        "win_rate": round(win_rate, 1),
        "avg_pnl": round(avg_pnl, 2),
    }


def get_history_as_dataframe(cache: dict) -> pd.DataFrame:
    """Flatten history into a DataFrame for display."""
    records = []
    for run in cache.get("runs", []):
        date = run.get("date", "")
        for pick in run.get("picks", []):
            records.append({
                "Entry Date": date,
                "Ticker": pick.get("Symbol", ""),
                "Strategy": pick.get("Strategy", ""),
                "Type": pick.get("Type", ""),
                "Source": pick.get("Source", ""),
                "Price": pick.get("Price"),
                "Target": pick.get("Target"),
                "Stop Loss": pick.get("Stop Loss"),
                "Status": pick.get("Status", "Active"),
                "Exit Price": pick.get("Exit Price"),
                "P&L (%)": pick.get("P&L (%)"),
                "Exit Date": pick.get("Exit Date", ""),
                "Validation Window": pick.get("Validation Window", 5),
            })
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def update_broker_stats(cache: dict, broker_name: str, success: bool):
    """Update per-broker win/loss stats."""
    stats = cache.get("broker_stats", {})
    if broker_name not in stats:
        stats[broker_name] = {"total": 0, "success": 0, "win_rate": 0.0}
    stats[broker_name]["total"] += 1
    if success:
        stats[broker_name]["success"] += 1
    stats[broker_name]["win_rate"] = round(
        (stats[broker_name]["success"] / stats[broker_name]["total"]) * 100, 1
    )
    cache["broker_stats"] = stats
    save_history_cache(cache)


def add_broker_call_to_history(cache: dict, broker: str, ticker: str, action: str, target: float, entry_date: str):
    """Add a broker call to history for tracking."""
    if "broker_history" not in cache:
        cache["broker_history"] = []
    cache["broker_history"].append({
        "Broker": broker,
        "Ticker": ticker,
        "Action": action,
        "Target": target,
        "Entry Date": entry_date,
        "Status": "Active",
        "Current Price": None,
        "P&L (%)": None,
    })
    save_history_cache(cache)


def validate_broker_calls(cache: dict, current_price_map: dict):
    """Validate all active broker calls against current prices."""
    if not cache.get("broker_history"):
        return

    updated = 0
    for call in cache["broker_history"]:
        if call.get("Status") != "Active":
            continue
        ticker = call.get("Ticker", "")
        current_price = current_price_map.get(ticker)
        if current_price is None:
            continue
        call["Current Price"] = round(current_price, 2)
        target = call.get("Target")
        entry_date = call.get("Entry Date", "")
        if target and entry_date:
            try:
                entry_dt = datetime.datetime.strptime(entry_date, "%Y-%m-%d")
                days_since = (datetime.date.today() - entry_dt.date()).days
                # Validate within 30 days
                if days_since > 30:
                    action = call.get("Action", "").lower()
                    if "buy" in action or "add" in action:
                        success = current_price >= target
                    elif "sell" in action or "reduce" in action:
                        success = current_price <= target
                    else:
                        success = False
                    call["Status"] = "Target Met" if success else "Stop Loss Hit"
                    call["P&L (%)"] = round(((current_price - float(call.get("Current Price", current_price))) / current_price) * 100, 2)
                    update_broker_stats(cache, call.get("Broker", "Unknown"), success)
                    updated += 1
            except Exception:
                pass

    if updated > 0:
        save_history_cache(cache)


def get_broker_stats_dataframe(cache: dict) -> pd.DataFrame:
    """Get broker stats as a DataFrame."""
    stats = cache.get("broker_stats", {})
    if not stats:
        return pd.DataFrame()
    records = []
    for broker_name, s in stats.items():
        records.append({
            "Broker": broker_name,
            "Total Calls": s["total"],
            "Successful": s["success"],
            "Win Rate (%)": s["win_rate"],
        })
    return pd.DataFrame(records).sort_values("Win Rate (%)", ascending=False).reset_index(drop=True)