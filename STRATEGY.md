# Strategy Research & Design Notes

This document explains the intraday and swing-trading strategies implemented in
NSE Pulse, the research rationale behind each, how risk is managed, and the
**known limitations** of running them on end-of-day (EOD) data. It is meant to be
read alongside `strategies.py` (the single source of truth for swing setups),
`intraday_screener.py`, and `optimizer.py`.

---

## 1. Trading styles & timeframes

| Style | Typical hold | Data granularity it *should* use | What this app uses |
|-------|--------------|----------------------------------|--------------------|
| Intraday | minutes–hours, flat by close | 1m / 5m / 15m bars + true session VWAP | **daily EOD bars** (proxy) |
| Short-term swing | 1–5 days | daily bars | daily bars ✅ |
| Medium-term swing | 15–30 days | daily / weekly bars | daily bars ✅ |

> **Important limitation.** The "intraday" screeners here run on *daily* candles
> because the app's free data source (yfinance EOD) does not provide reliable
> historical intraday bars for the whole NSE universe. As a result:
> - `VWAP` is a **rolling 20-day** volume-weighted average (a daily-chart
>   context filter), **not** an intraday session VWAP that resets at 09:15.
> - "ORB Breakout" uses the *previous day's high* rather than the first 15/30-min
>   opening range.
> - The 10-day intraday backtest models a **1-day hold** (exit at next day's
>   close if neither stop nor target is hit), not an intraday flat-by-close.
>
> These are reasonable **daily-chart proxies** for momentum/mean-reversion, but
> they are not a substitute for true intraday execution. See §6 for the upgrade
> path.

---

## 2. Indicators (see `screeners.calculate_indicators`)

All indicators use standard, widely-published parameters:

- **EMA 20 / 50 / 200** — trend structure. Price > EMA50 > EMA200 defines a
  healthy uptrend; EMA20 is the dynamic pullback line for swing entries.
- **RSI(14), Wilder smoothing** — momentum / overbought-oversold. <30 oversold,
  >70 overbought; the 40–60 band marks trend pullbacks.
- **MACD(12,26,9)** — momentum shifts; the histogram crossing above zero is the
  trigger.
- **Bollinger Bands(20, 2σ)** + **BB Width** — volatility envelope and squeeze
  detection (contraction → expansion).
- **ATR(14), Wilder** — volatility unit used to size *every* stop and target.
- **Volume Ratio** = volume / 20-day average volume — participation/conviction.
- **Supertrend(10, 3)** — ATR trailing-stop trend flip.
- **ADX(14) / +DI / −DI** — trend *strength* (ADX>25 = trending) and direction.

---

## 3. Swing setups (`strategies.py`)

Each setup is a trend-aligned entry with an ATR-scaled stop and target. Reward:risk
is **derived** from the ATR multipliers (`StrategySpec.risk_reward`), never typed
by hand.

| Setup | Core idea | Stop / Target (ATR) | R:R |
|-------|-----------|---------------------|-----|
| EMA Pullback (20) | Buy the dip to EMA20 in a confirmed uptrend | 1.5 / 2.0 | 1:1.33 |
| RSI Reversal (Oversold) | Oversold bounce (RSI<30→>30) above EMA200 | 1.0 / 1.8 | 1:1.80 |
| RSI Pullback (Uptrend) | RSI 38–55 ticking up in an uptrend + volume | 1.0 / 1.5 | 1:1.50 |
| Volume Breakout | New 20-day high on ≥2× volume, above EMA20 | 1.0 / 1.5 | 1:1.50 |
| MACD Crossover | Histogram turns positive, not overbought | 1.0 / 1.5 | 1:1.50 |
| Bollinger Rebound | Tag lower band, reclaim it with a green candle | 1.0 / 1.5 | 1:1.50 |
| Supertrend Reversal | Supertrend flips bullish while above EMA50 | 1.5 / 2.0 | 1:1.33 |
| ADX Trend Strength | ADX>25, +DI>−DI, RSI 45–65, above EMA20 | 1.5 / 2.0 | 1:1.33 |
| High-Conviction 95% Pullback | Tight target / wide stop pullback | 1.8 / 1.2 | 1:0.67 |

### Design principles (research-backed)

1. **Trade with the trend.** Every long requires price above EMA50 (and often
   EMA200). Pullback-in-uptrend and breakout-continuation are the two setups with
   the most durable published edge; counter-trend entries are avoided.
2. **Volatility-normalised risk.** Fixed-percent stops over-risk calm names and
   get whipsawed on volatile ones. ATR multiples adapt the stop to each stock's
   current regime. Trend-continuation setups use a wider 1.5-ATR stop to ride out
   noise; breakouts/mean-reversion use a tighter 1.0-ATR stop for a cleaner
   invalidation.
3. **Confirmation over prediction.** Breakouts demand a volume surge; reversals
   demand an actual up-close/green candle rather than anticipating the turn.

### ⚠️ Caveat on "High-Conviction 95% Pullback"

This setup deliberately uses a **tight 1.2-ATR target with a wide 1.8-ATR stop**
(R:R = 1:0.67). That maximises *hit rate* but the payoff is negative per unit of
risk: at a 65% win rate it only breaks even, and a single stop wipes out ~1.5
winners. The whole optimizer sorts by "Target Hit Rate", so this setup will look
attractive on the leaderboard while being fragile in live P&L. **Chasing a 95%
target-hit-rate is an anti-pattern** — see §5. Prefer setups with R:R ≥ 1:1.5 and
judge them on *expectancy* (`win% × avg_win − loss% × avg_loss`), not hit rate.

---

## 4. Intraday setups (`intraday_screener.py`)

Long: VWAP Bounce, ORB Breakout, EMA 9/21 Crossover.
Short: VWAP Rejection, Gap-Down Continuation, EMA 9/21 Crossover.

All use tight sub-1-ATR stops appropriate for a short hold, and shorts correctly
invert the stop (above entry) and target (below entry). Given the EOD-proxy
limitation (§1), treat these as **daily momentum/mean-reversion filters** rather
than executable intraday signals.

---

## 5. Backtesting caveats

The optimizer (`optimizer.py`) evaluates each individual setup plus every AND/OR
pair and 2/3/4-of-N consensus models. Read the leaderboard with these caveats:

- **Overfitting / multiple comparisons.** Testing dozens of combinations on one
  stock and picking the top by hit rate is p-hacking; the "winner" rarely
  survives out-of-sample. Prefer robustness across many names and time windows.
- **Hit rate ≠ profitability.** Optimise **expectancy** and Sharpe, not target
  hit rate. A 90% hit rate with 1:0.5 R:R loses money.
- **Fills are idealised.** Stops/targets are assumed to fill exactly at the level
  intra-bar; slippage, gaps through the stop, brokerage and STT/taxes are not
  modelled. Real results are worse.
- **Stop-vs-target ambiguity.** When a bar's range spans both stop and target,
  the engine conservatively assumes the **stop** hit first.
- **Survivorship & look-ahead.** Universes use *current* constituents; indicators
  are causal (no future leakage), which the regression harness verifies.

---

## 6. Recommended upgrade path

1. **Real intraday data** (1–5m bars) to make VWAP a true session VWAP and ORB a
   real opening-range breakout; add a hard end-of-day flat for intraday trades.
2. **Expectancy-based ranking** in the optimizer (add avg-win/avg-loss, profit
   factor, Sharpe, max drawdown) and de-emphasise raw hit rate.
3. **Walk-forward / out-of-sample validation** instead of single-window fitting.
4. **Position sizing** by fixed fractional risk (e.g. risk 1% of equity ÷ ATR
   stop distance) to convert signals into an executable, risk-managed system.

---

## 7. For contributors: where the numbers live

- Entry conditions + ATR stop/target multipliers for **all swing setups** are
  declared exactly once in `strategies.py` (`SPECS`). Both the live screeners
  (`screeners.py`) and the backtest optimizer (`optimizer.py`) consume that
  registry, so they can never drift apart again.
- Indicator math lives in `screeners.calculate_indicators` (memoised per frame).
- Regression safety: `scratch/golden_baseline.py` captures every screener /
  optimizer output on deterministic synthetic data — run `write` before a change
  and `check` after to prove behaviour is preserved.
