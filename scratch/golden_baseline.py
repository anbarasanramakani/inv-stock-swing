"""
Golden-output regression harness.

Generates deterministic synthetic OHLCV data (no network) and captures the
outputs of every pure screener/optimizer/intraday function so a refactor can be
proven behaviour-preserving. Run once before refactor to write the baseline,
then again after to diff.

Usage:
    python scratch/golden_baseline.py write   # save baseline
    python scratch/golden_baseline.py check   # compare against baseline
"""
import sys
import os
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import screeners as scr
import optimizer as opt
import intraday_screener as intra

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_baseline.json")


def make_df(seed: int, n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2023-01-02", periods=n)
    # Random walk with mild drift + occasional regime shifts to trigger signals.
    steps = rng.normal(0.0006, 0.018, n)
    steps[n // 3: n // 3 + 5] += 0.05       # a breakout burst
    steps[2 * n // 3: 2 * n // 3 + 4] -= 0.05  # a sharp dip
    close = 100 * np.exp(np.cumsum(steps))
    high = close * (1 + np.abs(rng.normal(0, 0.01, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.01, n)))
    openp = close * (1 + rng.normal(0, 0.008, n))
    vol = rng.integers(1_000_000, 5_000_000, n).astype(float)
    vol[n // 3: n // 3 + 5] *= 3            # volume spike on breakout
    df = pd.DataFrame(
        {"Open": openp, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )
    return df


def _round(obj):
    """Recursively round floats so numeric jitter never causes false diffs."""
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v) for v in obj]
    return obj


def capture() -> dict:
    out = {}
    for seed in range(8):
        ticker = f"SEED{seed}.NS"
        df = make_df(seed)

        ind = scr.calculate_indicators(df)
        ind_tail = None
        if ind is not None:
            cols = ["EMA20", "EMA50", "EMA200", "RSI", "MACD", "MACD_Signal",
                    "MACD_Hist", "BB_Upper", "BB_Lower", "BB_Width", "ATR",
                    "Vol_Ratio", "VWAP", "Supertrend", "ST_Direction",
                    "PlusDI", "MinusDI", "ADX"]
            ind_tail = ind[cols].tail(3).to_dict(orient="records")

        sum_df, trade_logs = opt.run_3month_optimization(df, hold_days=5, backtest_days=60, ticker="")

        out[ticker] = {
            "indicators_tail": ind_tail,
            "short_signal": scr.run_screener_on_data(ticker, df, "All Strategies"),
            "past_signals": scr.track_past_signals(ticker, df, "All Strategies"),
            "medium_term": scr.run_medium_term_screener(ticker, df),
            "intraday_live": intra.run_intraday_screener(ticker, df),
            "intraday_backtest": intra.backtest_intraday_10days(ticker, df),
            "opt_summary": sum_df.to_dict(orient="records") if not sum_df.empty else [],
            "opt_trade_counts": {k: len(v) for k, v in trade_logs.items()},
        }
    return _round(out)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    data = capture()
    if mode == "write":
        with open(BASELINE, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Baseline written: {BASELINE}")
        return

    with open(BASELINE) as f:
        base = json.load(f)
    new = json.loads(json.dumps(data, default=str))
    if base == new:
        print("GOLDEN OK — outputs identical to baseline.")
        return
    # Report first differences
    print("GOLDEN MISMATCH")
    for tk in base:
        for key in base[tk]:
            if base[tk][key] != new.get(tk, {}).get(key):
                print(f"  DIFF at {tk} / {key}")
                print(f"    base={json.dumps(base[tk][key])[:400]}")
                print(f"    new ={json.dumps(new.get(tk, {}).get(key))[:400]}")
    sys.exit(1)


if __name__ == "__main__":
    main()
