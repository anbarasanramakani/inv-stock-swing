import sys
import os
import pandas as pd

# Add workspace to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import tickers as tick
import data_provider as dp
import screeners as scr
import institutional as inst

def generate_backtests():
    print("==================================================")
    print("GENERATING 10-DAY BACKTESTS FOR OPTIMIZED & TIER-1")
    print("==================================================")
    
    # 1. Fetch Bulk Deals
    print("Loading recent bulk deals...")
    bulk_df = inst.get_recent_bulk_deals()
    if bulk_df is None:
        print("[WARNING] Bulk deals unavailable.")
        bulk_df = pd.DataFrame()
        
    # 2. Get tickers (Nifty 100 + any stock with bulk deals to ensure maximum Tier-1 coverage)
    print("Resolving tickers...")
    nifty50_tickers = tick.get_nifty50_tickers()
    nifty100_tickers = list(set(nifty50_tickers + [f"{sym}.NS" for sym in tick.FALLBACK_NIFTY_100]))
    
    bulk_symbols = bulk_df['Symbol'].unique().tolist() if not bulk_df.empty else []
    bulk_tickers = [f"{sym}.NS" for sym in bulk_symbols]
    
    # Combine to keep it extremely fast and highly targeted
    target_tickers = list(set(nifty100_tickers + bulk_tickers))
    print(f"Total target tickers for backtesting: {len(target_tickers)}")
    
    # 3. Download data
    print("Downloading historical data...")
    stock_data = dp.download_stock_data_batch(target_tickers, period="1y")
    print(f"Downloaded data for {len(stock_data)} / {len(target_tickers)} stocks.")
    
    # 4. Backtest parameters
    # Test over the past 10 trading days (N-11 to N-2)
    opt_records = []
    t1_records = []
    
    nifty50_syms = [s.replace(".NS", "").upper() for s in nifty50_tickers]
    
    strategies = [
        ("EMA Pullback (20)",     scr.SHORT_STRATEGIES["EMA Pullback (20)"]),
        ("RSI Pullback/Reversal", scr.SHORT_STRATEGIES["RSI Reversal & Pullback"]),
        ("Volume Breakout",       scr.SHORT_STRATEGIES["Volume Breakout"]),
        ("MACD Crossover",        scr.SHORT_STRATEGIES["MACD Crossover"]),
        ("Bollinger Rebound",     scr.SHORT_STRATEGIES["Bollinger Rebound"]),
    ]
    
    print("Analyzing daily slices for technical setups and institutional matching...")
    for ticker, df_raw in stock_data.items():
        df = scr.calculate_indicators(df_raw)
        if df is None or len(df) < 50:
            continue
            
        N = len(df)
        symbol = ticker.replace(".NS", "").upper()
        
        for idx in range(N-11, N-1):
            if idx < 20:
                continue
                
            slice_df = df.iloc[:idx+1].copy()
            trigger_date = df.index[idx]
            
            # Check setups
            for strat_name, strat_fn in strategies:
                matched, res = strat_fn(slice_df)
                if matched:
                    entry_price = res["Price"]
                    target = res["Target"]
                    sl = res["Stop Loss"]
                    
                    # Track forward to today
                    status = "Active"
                    days_held = 0
                    pnl_pct = 0.0
                    exit_price = entry_price
                    
                    for check_idx in range(idx+1, N):
                        days_held += 1
                        day_high = df['High'].iloc[check_idx]
                        day_low = df['Low'].iloc[check_idx]
                        
                        if day_low <= sl:
                            status = "Stop Loss Hit"
                            exit_price = sl
                            pnl_pct = ((sl - entry_price) / entry_price) * 100
                            break
                        elif day_high >= target:
                            status = "Target Hit"
                            exit_price = target
                            pnl_pct = ((target - entry_price) / entry_price) * 100
                            break
                            
                    if status == "Active":
                        exit_price = df['Close'].iloc[-1]
                        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                        
                    trade_record = {
                        "Trigger Date": trigger_date.strftime("%Y-%m-%d"),
                        "Ticker": symbol,
                        "Strategy": strat_name,
                        "Entry Price": round(entry_price, 2),
                        "Target": round(target, 2),
                        "Stop Loss": round(sl, 2),
                        "Current/Exit": round(exit_price, 2),
                        "P&L (%)": round(pnl_pct, 2),
                        "Status": status,
                        "Days Held": days_held
                    }
                    
                    # Check if it fits the Optimized Focus Group (Nifty 50 large-cap pullbacks/reversals)
                    is_opt_strat = strat_name in ["EMA Pullback (20)", "MACD Crossover", "RSI Pullback (Uptrend)", "RSI Reversal (Oversold)"]
                    if symbol in nifty50_syms and is_opt_strat:
                        opt_records.append(trade_record)
                        
                    # Check if it fits Tier-1 (Had bulk buy deal in 7 days prior to trigger)
                    if not bulk_df.empty:
                        symbol_deals = bulk_df[bulk_df['Symbol'] == symbol]
                        has_bulk_buy = False
                        deal_info = []
                        
                        for _, row in symbol_deals.iterrows():
                            deal_date = pd.to_datetime(row['Date'])
                            days_diff = (trigger_date - deal_date).days
                            
                            if row['Buy/Sell'] == 'BUY' and 0 <= days_diff <= 7:
                                has_bulk_buy = True
                                client = str(row['ClientName']).upper().strip()
                                qty = row['QuantityTraded']
                                prc = row['TradePrice/Wght.Avg.Price']
                                
                                # Format quantity
                                try:
                                    qty_val = f"{int(float(str(qty).replace(',', '').strip())):,}"
                                except:
                                    qty_val = str(qty)
                                try:
                                    prc_val = f"{float(str(prc).replace(',', '').strip()):.2f}"
                                except:
                                    prc_val = str(prc)
                                    
                                deal_info.append(f"{client} bought {qty_val} shares @ ₹{prc_val}")
                                
                        if has_bulk_buy:
                            t1_record = dict(trade_record)
                            t1_record["Institutional_Details"] = " | ".join(deal_info)
                            t1_records.append(t1_record)
                            
    # 5. Save results to CSVs
    opt_csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "opt_backtest_cache.csv")
    t1_csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "t1_backtest_cache.csv")
    
    pd.DataFrame(opt_records).to_csv(opt_csv_path, index=False)
    pd.DataFrame(t1_records).to_csv(t1_csv_path, index=False)
    
    print(f"[OK] Generated {len(opt_records)} Optimized Focus Group backtest trades.")
    print(f"[OK] Generated {len(t1_records)} Tier-1 High-Conviction backtest trades.")
    print("==================================================")

if __name__ == "__main__":
    generate_backtests()
