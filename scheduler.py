"""
scheduler.py
Scheduled Full Analysis runner for NSE Pulse.

This script runs the Full Analysis on Nifty 1000 at scheduled times.
Intended to be run via Windows Task Scheduler or cron.

Usage:
  python scheduler.py --mode full --universe "Nifty 1000" --strategy "All Strategies"
"""
import argparse
import datetime
import time
import sys
import json
import os

# Must run from project directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import data_provider as dp
import screeners as scr
import institutional as inst
import news_provider as news_helper
import intraday_screener as intra
import tickers as tick_helper
import analysis_history as hist

def run_full_scheduled_analysis():
    """Run Full Analysis on Nifty 1000 universe at scheduled times."""
    print(f"[{datetime.datetime.now()}] Starting scheduled Full Analysis on Nifty 1000...")
    
    all_nse_symbols = tick_helper.get_all_nse_tickers()
    
    # Load existing news cache
    existing_news_list = []
    if os.path.exists("news_cache.json"):
        try:
            with open("news_cache.json", "r", encoding="utf-8") as f:
                existing_news_list = json.load(f)
        except Exception:
            pass
    
    # Run news analysis
    news_picks = news_helper.get_today_news_recommendations(
        stock_data={},
        all_symbols=all_nse_symbols,
        existing_picks=existing_news_list,
    )
    
    # Download stock data in batches
    universe = tick_helper.get_nifty1000_tickers()
    print(f"[{datetime.datetime.now()}] Downloading data for {len(universe)} Nifty 1000 stocks...")
    
    data_cache = {}
    batch_size = 50
    for i in range(0, len(universe), batch_size):
        batch = universe[i:i+batch_size]
        try:
            batch_data = dp.download_stock_data_batch(batch, period="1y")
            data_cache.update(batch_data)
            print(f"[{datetime.datetime.now()}] Downloaded {len(batch_data)} stocks (batch {i//batch_size + 1})")
        except Exception as e:
            print(f"Error downloading batch {i//batch_size + 1}: {e}")
        time.sleep(0.5)
    
    # Run screeners
    swing_results = []
    past_signals = []
    medium_results = []
    intraday_picks = []
    
    print(f"[{datetime.datetime.now()}] Running screeners on {len(data_cache)} stocks...")
    
    bulk_deals = inst.get_recent_bulk_deals()
    
    for ticker, df in data_cache.items():
        try:
            res = scr.run_screener_on_data(ticker, df, "All Strategies")
            if res:
                swing_results.append(res)
            past_signals.extend(scr.track_past_signals(ticker, df, "All Strategies"))
            mt = scr.run_medium_term_screener(ticker, df)
            if mt:
                medium_results.append(mt)
            intra_res = intra.run_intraday_screener(ticker, df)
            if intra_res:
                intraday_picks.extend(intra_res)
        except Exception:
            continue
    
    swing_results = inst.enrich_picks_with_bulk_deals(swing_results, bulk_deals)
    medium_results = inst.enrich_picks_with_bulk_deals(medium_results, bulk_deals)
    
    # News backtest
    cached_computed_picks = [p for p in existing_news_list if p.get("Price") and p.get("Stop Loss") and p.get("Target")]
    news_bt = news_helper.run_news_backtest(data_cache, lookback_days=30, cached_news_items=cached_computed_picks)
    
    # Save to analysis history
    all_picks = []
    for p in swing_results:
        p_copy = dict(p)
        p_copy["Source"] = "swing"
        all_picks.append(p_copy)
    for p in medium_results:
        p_copy = dict(p)
        p_copy["Source"] = "medium"
        all_picks.append(p_copy)
    for p in intraday_picks:
        p_copy = dict(p)
        p_copy["Source"] = "intraday"
        all_picks.append(p_copy)
    for p in news_picks:
        p_copy = dict(p)
        p_copy["Source"] = "news"
        all_picks.append(p_copy)
    
    history_cache = hist.load_history_cache()
    hist.add_run_to_history(
        history_cache,
        date_str=datetime.date.today().isoformat(),
        universe="Nifty 1000",
        strategy="All Strategies",
        mode="scheduled",
        pick_list=all_picks,
    )
    
    # Persist news cache
    try:
        existing_map = {}
        if os.path.exists("news_cache.json"):
            with open("news_cache.json", "r", encoding="utf-8") as f:
                for item in json.load(f):
                    existing_map[item.get("Headline", "")] = item
        for p in news_picks:
            existing_map[p.get("Headline", "")] = p
        merged = list(existing_map.values())
        with open("news_cache.json", "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving news cache: {e}")
    
    print(f"[{datetime.datetime.now()}] Scheduled Full Analysis complete. Generated {len(swing_results)} swing picks, {len(medium_results)} medium-term, {len(news_picks)} news picks.")
    return len(swing_results)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NSE Pulse Scheduled Analysis")
    parser.add_argument("--mode", default="full", help="Analysis mode")
    parser.add_argument("--universe", default="Nifty 1000", help="Stock universe")
    parser.add_argument("--schedule-check", action="store_true", help="Only run if within 5 mins of scheduled time")
    args = parser.parse_args()
    
    if args.schedule_check:
        now = datetime.datetime.now()
        ist_hour, ist_min = now.hour, now.minute
        target_times = [(9, 20), (15, 30)]  # 9:20 IST and 15:30 IST
        is_target_time = any(
            ist_hour == h and abs(ist_min - m) <= 5
            for h, m in target_times
        )
        if not is_target_time:
            print(f"Not a scheduled time ({ist_hour}:{ist_min}). Skipping.")
            sys.exit(0)
    
    run_full_scheduled_analysis()