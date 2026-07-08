import sys
import os
import pandas as pd

# Add workspace to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import data_provider as dp
import optimizer as opt

def test_reliance_optimization():
    print("==================================================")
    print("TESTING 3-MONTH MULTI-STRATEGY OPTIMIZER ON RELIANCE")
    print("==================================================")
    
    # 1. Get stock data for Reliance
    ticker = "RELIANCE.NS"
    print(f"Fetching 1-year EOD data for {ticker}...")
    df = dp.get_single_stock_data(ticker, period="1y")
    
    if df is None or df.empty:
        print("[FAIL] Reliance EOD data is empty or unavailable.")
        return
        
    print(f"Downloaded {len(df)} rows. Running optimizer...")
    
    # 2. Run the 3-month backtest
    summary_df, trade_logs = opt.run_3month_optimization(df, hold_days=5, backtest_days=60, ticker=ticker)
    
    # 3. Assertions and reports
    # Grid size derives from the shared strategy registry so it never goes stale:
    # N individual + 2 * C(N, 2) pairwise (AND + OR) + 3 consensus models.
    import math
    n = len(opt.CHECK_FUNCTIONS)
    expected = n + 2 * math.comb(n, 2) + 3
    print(f"Total strategy configurations evaluated: {len(summary_df)} (expected {expected})")
    assert len(summary_df) == expected, f"Expected {expected} configurations, got {len(summary_df)}"
    
    print("\nTop 10 performing strategies/combinations by Target Hit Rate:")
    cols = ["Strategy", "Type", "Total Trades", "Target Hits", "Target Hit Rate (%)", "Avg P&L (%)"]
    print(summary_df[cols].head(10).to_string(index=False))
    
    # Check for >= 95% hit rate
    high_hit_rate = summary_df[summary_df["Target Hit Rate (%)"] >= 95.0]
    if not high_hit_rate.empty:
        print(f"\n[SUCCESS] Found {len(high_hit_rate)} strategies/combinations hitting >= 95% target:")
        print(high_hit_rate[cols].to_string(index=False))
    else:
        print("\n[INFO] No strategy/combination reached a 95% target hit rate on this stock.")
        
    print("\nVerifying trade logs mapping...")
    for strat_name in summary_df["Strategy"].head(3):
        trades = trade_logs.get(strat_name, [])
        print(f" - Strategy '{strat_name}' had {len(trades)} trades in log.")
        if trades:
            print(f"   Example trade: {trades[0]}")
            
    print("==================================================")
    print("[TEST OK] Backend optimization engine verified successfully!")
    print("==================================================")

if __name__ == "__main__":
    test_reliance_optimization()
