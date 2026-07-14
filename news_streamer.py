import asyncio
import json
from typing import AsyncGenerator, List
from schemas import MarketNewsItem, MarketStatusSummary
from news_service import InitialMarketNewsService

service = InitialMarketNewsService()

async def stream_news(interval: int = 60, max_items: int = 20) -> AsyncGenerator[dict, None]:
    """Asynchronously yield fresh news items.

    Parameters
    ----------
    interval: int
        Seconds between polling the news service.
    max_items: int
        Maximum number of items to emit per interval.
    """
    while True:
        try:
            summary: MarketStatusSummary = service.get_market_sentiment_and_news()
            items: List[MarketNewsItem] = summary.macro_headlines
            # Emit up to max_items recent items (newest first)
            for item in items[:max_items]:
                # Convert Pydantic model to plain dict for JSON transmission
                yield item.model_dump()
        except Exception as e:
            # Log and continue – Stream remains alive
            print(f"[news_streamer] error fetching news: {e}")
        await asyncio.sleep(interval)
