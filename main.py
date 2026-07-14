import json
from typing import Optional

import uvicorn
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from schemas import MarketStatusSummary
from news_service import InitialMarketNewsService
from analysis_engine import chunk_analysis_engine
from news_streamer import stream_news
import tickers as tick_helper
from scheduler import run_full_scheduled_analysis

app = FastAPI(
    title="NSE Pulse Terminal API",
    description="Asynchronous high-throughput financial data analysis pipeline.",
    version="1.0.0"
)

# Enable CORS for all domains to support microservice communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

news_service = InitialMarketNewsService()

@app.get("/api/v1/news/initial-load", response_model=MarketStatusSummary)
async def get_initial_load():
    """Fetch market sentiment and macro headlines for the UI initial load."""
    try:
        return news_service.get_market_sentiment_and_news()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading initial news: {str(e)}")
@app.get("/api/v1/news/stream")
async def news_stream_endpoint(interval: int = Query(60, description="Polling interval in seconds"), max_items: int = Query(20, description="Max items per poll")):
    """Stream fresh news items via Server‑Sent Events (SSE)."""
    async def generator():
        async for item in stream_news(interval=interval, max_items=max_items):
            yield {"event": "news", "data": json.dumps(item)}
    return EventSourceResponse(generator())

@app.get("/api/v1/stocks/analyze-stream")
async def analyze_stream(
    tickers: Optional[str] = Query(None, description="Comma-separated NSE tickers. Defaults to Nifty 50 if empty."),
    strategy: str = Query("All Strategies", description="Screener strategy name filter."),
    min_price: float = Query(20.0, description="Minimum price filter."),
    min_vol_ratio: float = Query(1.0, description="Minimum volume ratio filter.")
):
    """
    Asynchronous Server-Sent Events (SSE) stream endpoint.
    Downloads and analyzes stocks in 10-ticker batches, yielding results progressively.
    """
    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        # Append .NS suffix if missing
        ticker_list = [f"{t}.NS" if not t.endswith(".NS") else t for t in ticker_list]
    else:
        # Fallback to Nifty 50 constituents if empty
        ticker_list = tick_helper.get_nifty50_tickers()

    async def event_generator():
        try:
            async for progress in chunk_analysis_engine(
                ticker_list, strategy, min_price, min_vol_ratio, chunk_size=10
            ):
                # Yield Event source message
                yield {
                    "event": "message",
                    "data": progress.model_dump_json()
                }
        except Exception as e:
            print(f"Streaming error occurred: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"detail": str(e)})
            }

    return EventSourceResponse(event_generator())

@app.get("/api/v1/trigger-full-analysis")
async def trigger_full_analysis(
    background_tasks: BackgroundTasks,
    check_schedule: bool = Query(False, description="If true, only runs at 9:20 and 15:30 IST. Useful if UptimeRobot pings frequently.")
):
    """
    Trigger a full analysis run (e.g. from UptimeRobot). 
    Runs asynchronously in the background.
    """
    if check_schedule:
        import datetime
        now = datetime.datetime.now()
        ist_hour, ist_min = now.hour, now.minute
        target_times = [(9, 20), (15, 30)]
        is_target_time = any(
            ist_hour == h and abs(ist_min - m) <= 5
            for h, m in target_times
        )
        if not is_target_time:
            return {"status": "skipped", "message": f"Not a scheduled time ({ist_hour}:{ist_min}). Skipping."}

    background_tasks.add_task(run_full_scheduled_analysis)
    return {"status": "success", "message": "Full analysis triggered successfully in the background."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
