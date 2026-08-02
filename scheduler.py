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
    """Run Full Analysis on Nifty 1000 universe at scheduled times."""
    now_ist = _now_ist()
    print(f"[{now_ist.strftime('%Y-%m-%d %H:%M IST')}] Starting scheduled Full Analysis on Nifty 1000...")
    
    all_nse_symbols = tick_helper.get_all_nse_tickers()
    
    # Load existing news cache
    existing_news_list = []
    if _NEWS_CACHE_FILE.exists():
        try:
            with open(_NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
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
    # Also push analysis history to GitHub permanent cache so it survives Cloud restarts
    if _HAS_PCACHE:
        try:
            pcache.set_analysis_history(history_cache)
        except Exception as e:
            print(f"Error persisting analysis history to GitHub: {e}")
    
    # Persist news cache (local disk + GitHub for permanent storage)
    try:
        existing_map = {}
        if _NEWS_CACHE_FILE.exists():
            with open(_NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
                for item in json.load(f):
                    existing_map[item.get("Headline", "")] = item
        for p in news_picks:
            existing_map[p.get("Headline", "")] = p
        merged = list(existing_map.values())
        with open(_NEWS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        # Also push to GitHub permanent cache so it survives Cloud restarts
        if _HAS_PCACHE:
            pcache.set_news_cache(merged)
    except Exception as e:
        print(f"Error saving news cache: {e}")
    
    total_picks = len(swing_results) + len(medium_results) + len(intraday_picks) + len(news_picks)
    print(f"[{_now_ist().strftime('%Y-%m-%d %H:%M IST')}] Scheduled Full Analysis complete.")
    print(f"  Swing: {len(swing_results)} | Medium: {len(medium_results)} | Intraday: {len(intraday_picks)} | News: {len(news_picks)}")
    _write_last_run_status("success", total_picks)
    return len(swing_results)

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