import asyncio
import httpx
import json

async def test_progressive_analysis():
    # Target some standard tickers for testing (mixture of valid and invalid to verify error resilience)
    tickers = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "INVALID_TICKER", "SBIN", "TRENT", "HAL", "LT", "RVNL", "BHARTIARTL", "ETERNAL"]
    tickers_str = ",".join(tickers)
    
    url = f"http://127.0.0.1:8000/api/v1/stocks/analyze-stream?tickers={tickers_str}"
    
    print("==================================================")
    
    # 1. First verify initial news load endpoint
    print("Testing GET /api/v1/news/initial-load...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("http://127.0.0.1:8000/api/v1/news/initial-load", timeout=30.0)
            if resp.status_code == 200:
                data = resp.json()
                print(" [OK] News initial-load succeeded!")
                print(f"Market Sentiment Status: {data.get('market_status')}")
                print(f"Index Summary: {data.get('index_summary')}")
                print("Top 10 Headlines (sorted by date/time descending):")
                for idx, item in enumerate(data.get("macro_headlines", [])[:10], 1):
                    safe_title = item.get('title', '').encode('ascii', 'ignore').decode('ascii')
                    pub_at = item.get('published_at', '')
                    tickers_tagged = item.get('related_tickers', [])
                    tag_str = f" | Tagged Stocks: {', '.join(tickers_tagged)}" if tickers_tagged else ""
                    print(f"  {idx}. [{pub_at}] [{item.get('category')}] {safe_title}{tag_str}")
            else:
                print(f" [ERROR] Initial news load returned status: {resp.status_code}")
        except Exception as e:
            print(f" [ERROR] Connection to news endpoint failed: {repr(e)}")
            
    print("==================================================")
    
    # 2. Test SSE analysis stream endpoint
    print(f"Testing GET /api/v1/stocks/analyze-stream for {len(tickers)} stocks...")
    print(f"Connecting to: {url}")
    print("Waiting for streaming events...\n")
    
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(limits=limits, timeout=120.0) as client:
        try:
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    print(f" [ERROR] Failed to connect: Status code {response.status_code}")
                    return
                
                # Read stream lines
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        # Extract the data payload string
                        data_str = line[len("data:"):].strip()
                        if not data_str:
                            continue
                        
                        try:
                            payload = json.loads(data_str)
                            batch_idx = payload.get("batch_index")
                            tot_batches = payload.get("total_batches")
                            proc = payload.get("processed_count")
                            tot = payload.get("total_count")
                            
                            print(f" [BATCH] Received Batch {batch_idx}/{tot_batches} | Progress: {proc}/{tot} Stocks ({(proc/tot*100):.0f}%)")
                            print("--------------------------------------------------")
                            
                            for stock in payload.get("data", []):
                                ticker = stock.get("ticker")
                                price = stock.get("current_price")
                                change = stock.get("percent_change")
                                status = stock.get("analysis_status")
                                signal = stock.get("indicator_signals", {}).get("Signal", "HOLD")
                                
                                if status == "SUCCESS":
                                    print(f"  [+] {ticker:<12} | Price: Rs.{price:<8} | Chg: {change:>+6.2f}% | Signal: {signal}")
                                else:
                                    print(f"  [-] {ticker:<12} | [ ANALYSIS FAILED / TIMEOUT ]")
                            print("--------------------------------------------------\n")
                            
                        except Exception as parse_err:
                            print(f"Error parsing SSE line payload: {parse_err}")
                            print(f"Raw line: {line}")
                            
        except Exception as conn_err:
            print(f" [ERROR] Client connection failed: {conn_err}")
            print("Ensure you started the FastAPI server with: uvicorn main:app --reload")

if __name__ == "__main__":
    asyncio.run(test_progressive_analysis())
