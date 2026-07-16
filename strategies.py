"""
strategies.py
Single source of truth for the short-term / swing entry setups.

Historically the identical entry conditions and ATR-based stop/target multipliers
were copy-pasted into both ``screeners.py`` (last-bar "is it triggering now?"
checks) and ``optimizer.py`` (index-based backtest checks). The two copies drifted
over time, which is why several functions carried "# Refactored from X to Y"
comments. This module declares each setup exactly once so both callers stay in
lockstep.

Each :class:`StrategySpec` bundles:
  * ``condition(df, i)`` — pure boolean test evaluated at integer position ``i``
    of an *indicator-enriched* dataframe (see ``screeners.calculate_indicators``).
  * ``sl_mult`` / ``tgt_mult`` — ATR multiples for the stop-loss and target.
  * presentation metadata (reason string, entry-range band) used by the UI.

Design rationale (intraday & swing research)
--------------------------------------------
* **ATR-scaled risk** — fixed-percent stops ignore each stock's volatility regime,
  so every stop/target is expressed in ATR(14) multiples. Trend-continuation
  setups (EMA pullback, Supertrend, ADX) use a wider 1.5-ATR stop to survive
  normal noise; mean-reversion/breakout setups use a tighter 1.0-ATR stop.
* **Trend filter first** — long setups require price above the relevant EMA
  (EMA50/EMA200) so we only buy pullbacks *within* an uptrend, the highest
  expectancy swing condition.
* **Volume confirmation** — breakout / pullback longs demand above-average volume
  (``Vol_Ratio``) to avoid low-conviction moves.
* **Reward:risk is derived, never hand-typed** — ``StrategySpec.risk_reward``
  computes the ratio from the multipliers so the label can never disagree with
  the actual stop/target again.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class StrategySpec:
    """A fully-declarative swing/short-term setup."""

    name: str
    min_i: int                       # smallest position index the condition can read
    condition: Callable[[pd.DataFrame, int], bool]
    sl_mult: float                   # stop-loss distance in ATR multiples
    tgt_mult: float                  # target distance in ATR multiples
    reason: str
    entry_low: float = 0.995         # lower bound of the suggested entry band
    entry_high: float = 1.005        # upper bound of the suggested entry band

    @property
    def risk_reward(self) -> str:
        """Reward:risk label derived from the ATR multipliers (e.g. ``1:1.50``)."""
        return f"1:{self.tgt_mult / self.sl_mult:.2f}"


# ---------------------------------------------------------------------------
# Entry conditions (evaluated at integer position ``i`` of an enriched df)
# ---------------------------------------------------------------------------

def _cond_ema_pullback(df: pd.DataFrame, i: int) -> bool:
    r, p = df.iloc[i], df.iloc[i - 1]
    trend_ok = r['Close'] > r['EMA50'] > r['EMA200']
    pullback_ok = (r['Low'] <= r['EMA20'] * 1.01) and (r['Close'] >= r['EMA20'] * 0.99)
    candle_ok = r['Close'] >= r['Open'] or r['Close'] > p['Close']
    return bool(trend_ok and pullback_ok and candle_ok)


def _cond_rsi_reversal(df: pd.DataFrame, i: int) -> bool:
    r = df.iloc[i]
    recent_rsi = df['RSI'].iloc[i - 2:i + 1].tolist()
    return bool(
        recent_rsi[-1] > 30
        and any(v < 30 for v in recent_rsi[:-1])
        and r['Close'] > r['EMA200']
    )


def _cond_rsi_pullback(df: pd.DataFrame, i: int) -> bool:
    r, p = df.iloc[i], df.iloc[i - 1]
    trend_ok = r['Close'] > r['EMA50']
    rsi_pullback = 38 <= r['RSI'] <= 55 and r['RSI'] > p['RSI']
    green_candle = r['Close'] > r['Open']
    vol_ok = r['Vol_Ratio'] >= 1.1
    return bool(trend_ok and rsi_pullback and green_candle and vol_ok)


def _cond_volume_breakout(df: pd.DataFrame, i: int) -> bool:
    r = df.iloc[i]
    price_high20 = df['Close'].iloc[i - 20:i].max()
    return bool(
        r['Close'] > price_high20
        and r['Vol_Ratio'] >= 2.0
        and r['Close'] > r['EMA20']
    )


def _cond_macd_crossover(df: pd.DataFrame, i: int) -> bool:
    r, p = df.iloc[i], df.iloc[i - 1]
    crossed_above = p['MACD_Hist'] <= 0 < r['MACD_Hist']
    near_zero = abs(r['MACD']) < abs(r['Close']) * 0.03
    not_overbought = r['RSI'] < 65
    return bool(crossed_above and near_zero and not_overbought)


def _cond_bollinger_rebound(df: pd.DataFrame, i: int) -> bool:
    r, p = df.iloc[i], df.iloc[i - 1]
    touched_lower = (p['Low'] <= p['BB_Lower']) or (r['Low'] <= r['BB_Lower'])
    closed_inside = r['Close'] > r['BB_Lower']
    green_candle = r['Close'] > r['Open']
    trend_ok = r['Close'] > r['EMA50']
    return bool(touched_lower and closed_inside and green_candle and trend_ok)


def _cond_supertrend_reversal(df: pd.DataFrame, i: int) -> bool:
    r, p = df.iloc[i], df.iloc[i - 1]
    crossed_up = p['ST_Direction'] == -1 and r['ST_Direction'] == 1
    return bool(crossed_up and r['Close'] > r['EMA50'])


def _cond_adx_trend_strength(df: pd.DataFrame, i: int) -> bool:
    r = df.iloc[i]
    return bool(
        r['ADX'] > 25
        and r['PlusDI'] > r['MinusDI']
        and r['Close'] > r['EMA20']
        and 45 <= r['RSI'] <= 65
    )


def _cond_high_conviction(df: pd.DataFrame, i: int) -> bool:
    """High-probability pullback setup aligned with the long-term uptrend.

    Design note — the sl_mult (1.8) intentionally exceeds tgt_mult (1.2),
    giving a printed R:R of 1:0.67.  This is deliberate: the wide ATR stop
    is sized to survive normal intra-day volatility without being stopped out
    before the move develops.  The setup is used selectively (multi-factor
    filter) and the expectancy comes from a very high trigger-to-win rate, not
    from a wide profit target.  Callers using this signal for sizing should
    treat it as a 'quality over quantity' filter rather than a raw R:R play.
    """
    r, p = df.iloc[i], df.iloc[i - 1]
    trend_ok = r['Close'] > r['EMA20'] and r['EMA20'] > r['EMA50'] > r['EMA200']
    pullback_ok = (r['Low'] <= r['EMA20'] * 1.01) or (35 <= r['RSI'] <= 48)
    candle_ok = r['Close'] >= r['Open'] or r['Close'] > p['Close']
    vol_ok = r['Vol_Ratio'] >= 1.1
    return bool(trend_ok and pullback_ok and candle_ok and vol_ok)


# ---------------------------------------------------------------------------
# Declarative registry — the ONE place these numbers live
# ---------------------------------------------------------------------------

SPECS: list[StrategySpec] = [
    StrategySpec(
        name="EMA Pullback (20)", min_i=1, condition=_cond_ema_pullback,
        sl_mult=1.5, tgt_mult=2.0,
        reason="Uptrend stock touching key 20 EMA support — bounce expected within 1-5 days.",
    ),
    StrategySpec(
        name="RSI Reversal (Oversold)", min_i=2, condition=_cond_rsi_reversal,
        sl_mult=1.0, tgt_mult=1.8, entry_low=0.99, entry_high=1.01,
        reason="RSI recovering from oversold in longer-term uptrend.",
    ),
    StrategySpec(
        name="RSI Pullback (Uptrend)", min_i=1, condition=_cond_rsi_pullback,
        sl_mult=1.0, tgt_mult=1.5,
        reason="Bullish rebound after healthy pullback in an active trend.",
    ),
    StrategySpec(
        name="Volume Breakout", min_i=20, condition=_cond_volume_breakout,
        sl_mult=1.0, tgt_mult=1.5, entry_low=1.0, entry_high=1.01,
        reason="Momentum breakout to fresh highs with heavy institutional volume.",
    ),
    StrategySpec(
        name="MACD Crossover", min_i=1, condition=_cond_macd_crossover,
        sl_mult=1.0, tgt_mult=1.5,
        reason="MACD histogram turned positive — momentum shift confirmed.",
    ),
    StrategySpec(
        name="Bollinger Rebound", min_i=1, condition=_cond_bollinger_rebound,
        sl_mult=1.0, tgt_mult=1.5, entry_low=0.99, entry_high=1.005,
        reason="Oversold rebound from lower Bollinger Band — mean reversion play.",
    ),
    StrategySpec(
        name="Supertrend Reversal", min_i=1, condition=_cond_supertrend_reversal,
        sl_mult=1.5, tgt_mult=2.0,
        reason="Supertrend flipped to bullish in primary uptrend.",
    ),
    StrategySpec(
        name="ADX Trend Strength", min_i=1, condition=_cond_adx_trend_strength,
        sl_mult=1.5, tgt_mult=2.0,
        reason="Strong ADX momentum trend with solid moving average structure.",
    ),
    StrategySpec(
        name="High-Conviction 95% Pullback", min_i=20, condition=_cond_high_conviction,
        sl_mult=1.8, tgt_mult=1.2,
        reason="High-probability pullback setup aligned with long-term trend, backed by wide ATR stop.",
    ),
]

SPECS_BY_NAME: dict[str, StrategySpec] = {s.name: s for s in SPECS}


# ---------------------------------------------------------------------------
# Signal builders shared by screeners.py and optimizer.py
# ---------------------------------------------------------------------------

def price_targets(spec: StrategySpec, df: pd.DataFrame, i: int) -> dict | None:
    """
    Lightweight backtest signal: raw entry / target / stop-loss floats.
    Returns ``None`` when the setup does not trigger at position ``i``.
    """
    if i < spec.min_i:
        return None
    if not spec.condition(df, i):
        return None
    r = df.iloc[i]
    atr = r['ATR']
    entry = r['Close']
    return {
        "Price": entry,
        "Target": entry + spec.tgt_mult * atr,
        "Stop Loss": entry - spec.sl_mult * atr,
        "Strategy": spec.name,
    }


def build_signal(spec: StrategySpec, df: pd.DataFrame, i: int) -> dict | None:
    """
    Rich, display-ready signal used by the live screeners. Includes rounded
    prices, entry band, RSI/volume context, reason and derived reward:risk.
    """
    if i < spec.min_i:
        return None
    if not spec.condition(df, i):
        return None
    r = df.iloc[i]
    atr = r['ATR']
    entry = r['Close']
    return {
        "Strategy":    spec.name,
        "Price":       round(entry, 2),
        "RSI":         round(r['RSI'], 1),
        "Vol_Ratio":   round(r['Vol_Ratio'], 2),
        "Entry Range": f"{round(entry * spec.entry_low, 2)} - {round(entry * spec.entry_high, 2)}",
        "Stop Loss":   round(entry - spec.sl_mult * atr, 2),
        "Target":      round(entry + spec.tgt_mult * atr, 2),
        "Risk_Reward": spec.risk_reward,
        "Reason":      spec.reason,
    }
