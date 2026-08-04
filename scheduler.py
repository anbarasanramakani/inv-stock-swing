"""
scheduler.py
Scheduled Full Analysis runner for NSE Pulse.

Run via GitHub Actions (.github/workflows/daily_analysis.yml) at 9:20 AM IST
every weekday (Mon-Fri). Can also be run manually or via Windows Task Scheduler.

GitHub Actions sets GITHUB_TOKEN and GITHUB_REPO env vars automatically.

Usage:
  python scheduler.py --mode full --universe "Nifty 1000" --strategy "All Strategies"
"""
import argparse
import datetime
import time
import sys
import json
import os
from pathlib import Path

# Must run from project directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── IST timezone (via pytz if available, fallback to UTC+5:30 offset) ──────────
try:
    import pytz
    _IST = pytz.timezone("Asia/Kolkata")
    def _now_ist():
        return datetime.datetime.now(_IST)
except ImportError:
    _UTC_OFFSET = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    def _now_ist():
        return datetime.datetime.now(_UTC_OFFSET)

# ── Inject GITHUB_TOKEN from env into github_cache before importing it ──────────
# GitHub Actions exposes the token as GITHUB_TOKEN env var.
# github_cache._get_config() already reads os.environ["GITHUB_TOKEN"] as fallback.
_gh_token_env = os.environ.get("GITHUB_TOKEN", "")
_gh_repo_env  = os.environ.get("GITHUB_REPO", "")
if _gh_token_env:
    # Pre-seed the module-level cached values so background threads can find them
    os.environ["GITHUB_TOKEN"] = _gh_token_env
if _gh_repo_env:
    os.environ["GITHUB_REPO"] = _gh_repo_env

_PROJECT_DIR = Path(__file__).parent
_NEWS_CACHE_FILE = _PROJECT_DIR / "news_cache.json"

import data_provider as dp
import screeners as scr
import institutional as inst
import news_provider as news_helper
import intraday_screener as intra
import tickers as tick_helper
import analysis_history as hist

# Multi-tier persistent cache (survives Streamlit Cloud restarts/deploys)
try:
    import persistent_cache as pcache
    _HAS_PCACHE = True
except ImportError:
    pcache = None
    _HAS_PCACHE = False


_LAST_RUN_FILE = Path(__file__).parent / ".last_scheduled_run.json"


def _write_last_run_status(status: str, picks_count: int = 0):
    """Write last run info to a small JSON file for the Streamlit sidebar badge."""
    try:
        with open(_LAST_RUN_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": _now_ist().strftime("%Y-%m-%d %H:%M IST"),
                "status": status,
                "picks": picks_count,
            }, f)
    except Exception as e:
        print(f"[Scheduler] Could not write last-run file: {e}")


def run_full_scheduled_analysis():
    """Run Full Analysis on Nifty 1000 universe — aligned with app.py worker logic.

    This mirrors _run_background_analysis_worker() in app.py so that scheduled
    runs produce identical picks, Damodaran signals, broker caches, and
    backtests compared to an interactive "Run Full Analysis" in the UI.
    """
    now_ist = _now_ist()
    print(f"[{now_ist.strftime('%Y-%m-%d %H:%M IST')}] Starting scheduled Full Analysis on Nifty 1000...")

    # ── 1. Resolve universe ──────────────────────────────────────────────────
    all_nse_symbols = tick_helper.get_all_nse_tickers()
    universe = tick_helper.get_nifty1000_tickers()
    print(f"[{_now_ist().strftime('%H:%M IST')}] Universe: {len(universe)} Nifty 1000 stocks")

    # ── 2. Download stock data in batches ────────────────────────────────────
    data_cache = {}
    batch_size = 10  # Match app.py worker (was 50 — too aggressive for memory)
    total_batches = (len(universe) + batch_size - 1) // batch_size
    for i in range(0, len(universe), batch_size):
        batch = universe[i:i + batch_size]
        batch_num = i // batch_size + 1
        try:
            batch_data = dp.download_stock_data_batch(batch, period="1y")
            data_cache.update(batch_data)
            print(f"  Batch {batch_num}/{total_batches}: downloaded {len(batch_data)} stocks")
        except Exception as e:
            print(f"  Batch {batch_num}/{total_batches}: ERROR - {e}")
        time.sleep(0.3)

    print(f"[{_now_ist().strftime('%H:%M IST')}] Downloaded {len(data_cache)} stocks total")

    # ── 3. Fetch institutional bulk deals ────────────────────────────────────
    bulk_deals = None
    try:
        bulk_deals = inst.get_recent_bulk_deals()
    except Exception as bd_err:
        print(f"[Bulk Deals] Fetch failed: {bd_err}")

    # ── 4. Run ALL screeners on every stock ──────────────────────────────────
    # Matches app.py: run_all_strategies_for_ticker + Damodaran + intraday
    swing_results = []
    past_signals = []
    medium_results = []
    intraday_picks = []
    intraday_backtest = []
    damodaran_picks = []
    processed = 0

    print(f"[{_now_ist().strftime('%H:%M IST')}] Running screeners on {len(data_cache)} stocks...")

    for ticker, df in data_cache.items():
        try:
            # ── Swing: ALL matching strategies (not just the first) ──
            all_strat_results = scr.run_all_strategies_for_ticker(
                ticker, df, "All Strategies"
            )
            for res in all_strat_results:
                swing_results.append(res)

            # ── Past signals tracking ──
            past_sigs = scr.track_past_signals(ticker, df, "All Strategies")
            if past_sigs:
                past_signals.extend(past_sigs)

            # ── Medium-term screener ──
            mt = scr.run_medium_term_screener(ticker, df)
            if mt:
                medium_results.append(mt)

            # ── Intraday screener ──
            intra_res = intra.run_intraday_screener(ticker, df)
            if intra_res:
                intraday_picks.extend(intra_res)

            # ── Intraday backtest (10-day) ──
            intra_bt = intra.backtest_intraday_10days(ticker, df)
            if intra_bt:
                intraday_backtest.extend(intra_bt)

            # ── Damodaran G4/G5 techniques ──
            dam_res = scr.run_damodaran_screener(ticker, df)
            if dam_res:
                damodaran_picks.extend(dam_res)

        except Exception:
            continue

        processed += 1
        if processed % 100 == 0:
            print(f"  Screened {processed}/{len(data_cache)} stocks...")

    print(f"[{_now_ist().strftime('%H:%M IST')}] Screening complete: "
          f"Swing={len(swing_results)} Medium={len(medium_results)} "
          f"Intraday={len(intraday_picks)} Damodaran={len(damodaran_picks)}")

    # ── 5. Enrich with institutional bulk deals ──────────────────────────────
    try:
        swing_results = inst.enrich_picks_with_bulk_deals(swing_results, bulk_deals)
        medium_results = inst.enrich_picks_with_bulk_deals(medium_results, bulk_deals)
    except Exception as enrich_err:
        print(f"[Enrichment] Failed: {enrich_err}")

    # ── 6. News analysis (with real stock data — was passing {} before) ──────
    # Load existing news from persistent cache first
    existing_news_list = []
    if _HAS_PCACHE:
        try:
            existing_news_list = pcache.get_news_cache() or []
        except Exception:
            pass
    if not existing_news_list and _NEWS_CACHE_FILE.exists():
        try:
            with open(_NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
                existing_news_list = json.load(f)
        except Exception:
            pass

    news_picks = []
    try:
        news_picks = news_helper.get_today_news_recommendations(
            stock_data=data_cache,  # FIX: Pass real stock data (was {} before)
            all_symbols=all_nse_symbols,
            existing_picks=existing_news_list,
        ) or []
        print(f"  News picks: {len(news_picks)}")
    except Exception as news_err:
        print(f"[News] Error: {news_err}")

    # ── 7. News backtest ─────────────────────────────────────────────────────
    news_backtest = []
    try:
        cached_computed = [p for p in existing_news_list
                          if p.get("Price") and p.get("Stop Loss") and p.get("Target")]
        news_backtest = news_helper.run_news_backtest(
            data_cache, lookback_days=30, cached_news_items=cached_computed
        ) or []
    except Exception as nbt_err:
        print(f"[News Backtest] Error: {nbt_err}")

    # ── 8. Broker recommendations fetch + persist ────────────────────────────
    try:
        broker_calls = news_helper.fetch_broker_calls(
            all_symbols=all_nse_symbols, max_items=60
        ) or []
        print(f"  Broker calls fetched: {len(broker_calls)}")

        # Merge with existing cached broker calls, prune to 30 days
        existing_brokers = []
        if _HAS_PCACHE:
            try:
                existing_brokers = pcache.get_brokers_cache() or []
            except Exception:
                pass
        existing_map = {item.get("Headline", ""): item for item in existing_brokers}
        for _p in broker_calls:
            existing_map[_p.get("Headline", "")] = _p
        merged_brokers = list(existing_map.values())
        try:
            merged_brokers = news_helper.prune_cache_by_days(
                merged_brokers, days=30, date_key='Date'
            )
        except Exception:
            pass
        # Persist via all tiers
        if _HAS_PCACHE:
            pcache.set_brokers_cache(merged_brokers)
        # Also save local file
        try:
            brokers_file = _PROJECT_DIR / "brokers_cache.json"
            with open(brokers_file, "w", encoding="utf-8") as f:
                json.dump(merged_brokers, f, indent=2, ensure_ascii=False, default=str)
        except Exception:
            pass
    except Exception as broker_err:
        print(f"[Broker Calls] Error: {broker_err}")

    # ── 9. Persist merged news cache ─────────────────────────────────────────
    try:
        merged_news_map = {
            item.get("Headline", item.get("headline", "")): item
            for item in existing_news_list
        }
        for item in news_picks:
            merged_news_map[item.get("Headline", item.get("headline", ""))] = item
        merged_news = list(merged_news_map.values())

        with open(_NEWS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(merged_news, f, indent=2, ensure_ascii=False, default=str)
        if _HAS_PCACHE:
            pcache.set_news_cache(merged_news)
    except Exception as e:
        print(f"[News Cache] Error saving: {e}")

    # ── 10. Build pick list and save to analysis history ─────────────────────
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
    for p in damodaran_picks:
        p_copy = dict(p)
        p_copy["Source"] = "damodaran"
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

    # Validate broker calls against current prices
    current_price_map = {}
    for pick in all_picks:
        ticker = pick.get("Ticker") or pick.get("Symbol") or ""
        price = pick.get("Price")
        if ticker and price:
            try:
                current_price_map[ticker] = float(price)
            except (ValueError, TypeError):
                pass
    hist.validate_broker_calls(history_cache, current_price_map)

    # FIX: Use save_history_cache() which writes both local file AND GitHub API
    hist.save_history_cache(history_cache)

    # ── 11. Summary ──────────────────────────────────────────────────────────
    total_picks = len(all_picks)
    print(f"\n[{_now_ist().strftime('%Y-%m-%d %H:%M IST')}] ══ Scheduled Full Analysis COMPLETE ══")
    print(f"  Swing:     {len(swing_results)}")
    print(f"  Medium:    {len(medium_results)}")
    print(f"  Intraday:  {len(intraday_picks)}")
    print(f"  Damodaran: {len(damodaran_picks)}")
    print(f"  News:      {len(news_picks)}")
    print(f"  TOTAL:     {total_picks}")
    _write_last_run_status("success", total_picks)
    return total_picks

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NSE Pulse Scheduled Analysis")
    parser.add_argument("--mode",            default="full",       help="Analysis mode")
    parser.add_argument("--universe",        default="Nifty 1000", help="Stock universe")
    parser.add_argument("--strategy",        default="All Strategies", help="Strategy filter")
    parser.add_argument("--schedule-check",  action="store_true",  help="Only run at 9:20 IST (±5 min)")
    parser.add_argument("--weekdays-only",   action="store_true",  help="Skip weekends (Sat/Sun)")
    args = parser.parse_args()

    now_ist = _now_ist()

    # ── Weekday guard ──────────────────────────────────────────────────────────
    if args.weekdays_only and now_ist.weekday() >= 5:   # 5=Sat, 6=Sun
        print(f"Weekend ({now_ist.strftime('%A')}). Skipping.")
        sys.exit(0)

    # ── Time-window guard ──────────────────────────────────────────────────────
    if args.schedule_check:
        ist_hour, ist_min = now_ist.hour, now_ist.minute
        target_times = [(9, 20), (15, 30)]  # 9:20 AM and 3:30 PM IST
        is_target_time = any(
            ist_hour == h and abs(ist_min - m) <= 5
            for h, m in target_times
        )
        if not is_target_time:
            print(f"Not a scheduled time ({ist_hour:02d}:{ist_min:02d} IST). Skipping.")
            sys.exit(0)

    try:
        run_full_scheduled_analysis()
    except Exception as exc:
        _write_last_run_status(f"error: {exc}")
        print(f"[Scheduler] FATAL ERROR: {exc}")
        raise