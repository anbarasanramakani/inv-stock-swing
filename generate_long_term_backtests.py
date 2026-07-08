import sys
import os
import pandas as pd

# Add workspace to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import tickers as tick
import data_provider as dp
import screeners as scr
import institutional as inst

def generate_long_term_backtests():
    print("==================================================")
    print("GENERATING 2-MONTH BACKTESTS FOR MEDIUM-TERM SETUP")
    print("==================================================")
    
    # 1. Fetch Bulk Deals
    print("Loading recent bulk deals...")
    bulk_df = inst.get_recent_bulk_deals()
    if bulk_df is None:
        bulk_df = pd.DataFrame()
        
    # 2. Get tickers (Nifty 100 + any stock with bulk deals to make it very targeted)
    print("Resolving tickers...")
    nifty50_tickers = tick.get_nifty50_tickers()
    nifty100_tickers = list(set(nifty50_tickers + [f"{sym}.NS" for sym in tick.FALLBACK_NIFTY_100]))
    
    bulk_symbols = bulk_df['Symbol'].unique().tolist() if not bulk_df.empty else []
    bulk_tickers = [f"{sym}.NS" for sym in bulk_symbols]
    
    target_tickers = list(set(nifty100_tickers + bulk_tickers))
    print(f"Total target tickers: {len(target_tickers)}")
    
    # 3. Download data
    print("Downloading historical data...")
    stock_data = dp.download_stock_data_batch(target_tickers, period="1y")
    print(f"Downloaded data for {len(stock_data)} / {len(target_tickers)} stocks.")
    
    # 4. Backtest parameters
    # Test over the past 40 trading days (approx 2 calendar months: N-41 to N-2)
    records = []
    
    strategies = [
        ("EMA Crossover (20/50)", scr.screen_ema_crossover),
        ("BB Squeeze Breakout", scr.screen_bb_squeeze_breakout)
    ]
    
    print("Analyzing daily slices over the past 2 months...")
    for ticker, df_raw in stock_data.items():
        df = scr.calculate_indicators(df_raw)
        if df is None or len(df) < 50:
            continue
            
        N = len(df)
        symbol = ticker.replace(".NS", "").upper()
        
        # Scan N-41 to N-2
        for idx in range(N-41, N-1):
            if idx < 30:
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
                    
                    # Track forward for up to 20 trading days (approx 1 calendar month)
                    status = "Active"
                    days_held = 0
                    pnl_pct = 0.0
                    exit_price = entry_price
                    
                    # Track forward up to index N
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
                            
                        # Exit after 20 trading days (approx 1 calendar month)
                        if days_held >= 20:
                            status = "Time Exit"
                            exit_price = df['Close'].iloc[check_idx]
                            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                            break
                            
                    if status == "Active":
                        exit_price = df['Close'].iloc[-1]
                        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                        
                    # Check bulk deals
                    has_bulk_buy = False
                    deal_info = []
                    if not bulk_df.empty:
                        symbol_deals = bulk_df[bulk_df['Symbol'] == symbol]
                        for _, row in symbol_deals.iterrows():
                            deal_date = pd.to_datetime(row['Date'])
                            days_diff = (trigger_date - deal_date).days
                            if row['Buy/Sell'] == 'BUY' and 0 <= days_diff <= 7:
                                has_bulk_buy = True
                                client = str(row['ClientName']).upper().strip()
                                qty = row['QuantityTraded']
                                prc = row['TradePrice/Wght.Avg.Price']
                                
                                try:
                                    qty_val = f"{int(float(str(qty).replace(',', '').strip())):,}"
                                except:
                                    qty_val = str(qty)
                                try:
                                    prc_val = f"{float(str(prc).replace(',', '').strip()):.2f}"
                                except:
                                    prc_val = str(prc)
                                    
                                deal_info.append(f"{client} bought {qty_val} shares @ ₹{prc_val}")
                                
                    records.append({
                        "Trigger Date": trigger_date.strftime("%Y-%m-%d"),
                        "Ticker": symbol,
                        "Strategy": strat_name,
                        "Entry Price": round(entry_price, 2),
                        "Target": round(target, 2),
                        "Stop Loss": round(sl, 2),
                        "Current/Exit": round(exit_price, 2),
                        "P&L (%)": round(pnl_pct, 2),
                        "Status": status,
                        "Days Held": days_held,
                        "High_Conviction": has_bulk_buy,
                        "Institutional_Details": " | ".join(deal_info) if has_bulk_buy else "No recent bulk deals"
                    })
                    
    # 5. Save cache CSV
    long_term_csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "long_term_backtest_cache.csv")
    pd.DataFrame(records).to_csv(long_term_csv_path, index=False)
    
    print(f"[OK] Generated {len(records)} long term backtest trades.")
    print("==================================================")

if __name__ == "__main__":
    generate_long_term_backtests()
