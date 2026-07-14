from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from enum import Enum

class NewsCategory(str, Enum):
    MACRO = "MACRO"
    SECTOR = "SECTOR"
    STOCK = "STOCK"

class MarketNewsItem(BaseModel):
    title: str
    summary: str
    source: str
    url: str
    published_at: str
    category: NewsCategory
    related_tickers: List[str] = Field(default_factory=list)
    price: Optional[float] = None
    target: Optional[float] = None
    stop_loss: Optional[float] = None
    risk_reward: Optional[str] = None
    entry_range: Optional[str] = None
    sentiment: Optional[str] = None

class MarketStatus(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

class MarketStatusSummary(BaseModel):
    market_status: MarketStatus
    index_summary: Dict[str, float]  # e.g., {"NIFTY 50": 24398.7, "SENSEX": 80234.1}
    macro_headlines: List[MarketNewsItem]

class AnalysisStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"

class StockAnalysisResult(BaseModel):
    ticker: str
    current_price: Optional[float] = None
    percent_change: Optional[float] = None
    indicator_signals: Dict[str, str] = Field(default_factory=dict)
    news_sentiment: Optional[str] = None
    analysis_status: AnalysisStatus

class StreamProgressPayload(BaseModel):
    batch_index: int
    total_batches: int
    processed_count: int
    total_count: int
    data: List[StockAnalysisResult]
