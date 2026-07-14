import asyncio
from typing import List, AsyncGenerator
import data_provider as dp
import screeners as scr
from schemas import StockAnalysisResult, StreamProgressPayload, AnalysisStatus

async def chunk_analysis_engine(
    tickers: List[str],
    strategy: str = "All Strategies",
    min_price: float = 20.0,
    min_vol_ratio: float = 1.0,
    chunk_size: int = 10
) -> AsyncGenerator[StreamProgressPayload, None]:
    """
    Progressively chunks up to 1,000 tickers into batches of 10,
    downloads and screens each batch concurrently, and yields
    StreamProgressPayload objects for progressive SSE updates.
    """
    total_count = len(tickers)
    if total_count == 0:
        return

    total_batches = (total_count + chunk_size - 1) // chunk_size
    processed_count = 0

    for batch_idx in range(total_batches):
        chunk = tickers[batch_idx * chunk_size : (batch_idx + 1) * chunk_size]
        
        # Download data for chunk asynchronously (run yfinance download in worker thread)
        try:
            chunk_data = await asyncio.to_thread(
                dp.download_stock_data_batch, chunk, "1y"
            )
        except Exception as e:
            print(f"Error downloading batch {batch_idx + 1}: {e}")
            chunk_data = {}

        batch_results = []
        for ticker in chunk:
            try:
                df = chunk_data.get(ticker)
                if df is None or df.empty:
                    batch_results.append(
                        StockAnalysisResult(
                            ticker=ticker,
                            analysis_status=AnalysisStatus.FAILED
                        )
                    )
                    continue

                # Run indicator calculations in worker thread to prevent block
                df_with_indicators = await asyncio.to_thread(scr.calculate_indicators, df)
                if df_with_indicators is None or df_with_indicators.empty:
                    batch_results.append(
                        StockAnalysisResult(
                            ticker=ticker,
                            analysis_status=AnalysisStatus.FAILED
                        )
                    )
                    continue

                last_price = float(df_with_indicators['Close'].iloc[-1])
                if last_price < min_price:
                    batch_results.append(
                        StockAnalysisResult(
                            ticker=ticker,
                            analysis_status=AnalysisStatus.FAILED
                        )
                    )
                    continue

                # Run screener matching rules
                res = scr.run_screener_on_data(ticker, df_with_indicators, strategy)
                
                # Fetch live LTP quote
                symbol_clean = ticker.replace(".NS", "")
                ltp = await asyncio.to_thread(dp.get_live_ltp, symbol_clean)
                if ltp is None:
                    ltp = last_price

                pclose = float(df_with_indicators['Close'].iloc[-2]) if len(df_with_indicators) > 1 else last_price
                percent_change = ((ltp - pclose) / pclose * 100) if pclose else 0.0

                # Assemble dynamic indicators signal payload
                indicator_signals = {
                    "MACD": "Bullish Crossover" if res and "MACD" in res.get("Reason", "") else "Neutral",
                    "RSI": f"{float(df_with_indicators['RSI'].iloc[-1]):.1f}" if "RSI" in df_with_indicators.columns else "—",
                    "VWAP": f"₹{float(df_with_indicators['VWAP'].iloc[-1]):.2f}" if "VWAP" in df_with_indicators.columns else "—",
                    "Vol_Ratio": f"{float(df_with_indicators['Vol_Ratio'].iloc[-1]):.1f}x" if "Vol_Ratio" in df_with_indicators.columns else "—",
                }

                # Evaluate strategy match and add to signals if trigger occurred
                if res and float(res.get('Vol_Ratio', 0)) >= min_vol_ratio:
                    indicator_signals["Signal"] = res.get("Strategy", "Triggered")
                    indicator_signals["Reason"] = res.get("Reason", "Setup matches strategy rules.")
                else:
                    indicator_signals["Signal"] = "HOLD"
                    indicator_signals["Reason"] = "No active technical breakout detected."

                batch_results.append(
                    StockAnalysisResult(
                        ticker=ticker,
                        current_price=round(ltp, 2),
                        percent_change=round(percent_change, 2),
                        indicator_signals=indicator_signals,
                        news_sentiment=res.get("Sentiment", "Positive") if res else "Neutral",
                        analysis_status=AnalysisStatus.SUCCESS
                    )
                )
            except Exception as ex:
                print(f"Error screening ticker {ticker}: {ex}")
                batch_results.append(
                    StockAnalysisResult(
                        ticker=ticker,
                        analysis_status=AnalysisStatus.FAILED
                    )
                )

        processed_count += len(chunk)
        
        # Yield progressive update payload
        yield StreamProgressPayload(
            batch_index=batch_idx + 1,
            total_batches=total_batches,
            processed_count=processed_count,
            total_count=total_count,
            data=batch_results
        )
