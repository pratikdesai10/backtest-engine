"""Nifty Momentum strategy: EMA Crossover + Momentum Candle for 5-min intraday.

Core Idea: Enter on strong EMA crossovers confirmed by an outsized candle body,
exit on a faster EMA crossover (momentum fade) or session close.

Entry: EMA(21) crosses EMA(50) while a momentum candle fires (body > 2.5x avg body).
Exit: Fast EMA(8) crosses EMA(13) in opposite direction, or end of session.

Designed for Nifty 5-min charts to generate directional signals for options buying.
Backtested 2020-2025: ~50% win rate, 1.6+ PF, 1.5+ RR, <6% max drawdown.
"""

from typing import Any

import pandas as pd

from src.indicators import ema_tv
from src.pine_translator import generate_pine_header
from src.strategy import SignalColumns, Strategy, StrategyType


class NiftyMomentum(Strategy):
    """EMA crossover + momentum candle strategy for Nifty 5-min intraday."""

    def __init__(
        self,
        entry_ema_fast: int = 21,
        entry_ema_slow: int = 50,
        candle_mult: float = 2.5,
        candle_avg_len: int = 15,
        exit_ema_fast: int = 8,
        exit_ema_slow: int = 13,
    ):
        self._entry_ema_fast = entry_ema_fast
        self._entry_ema_slow = entry_ema_slow
        self._candle_mult = candle_mult
        self._candle_avg_len = candle_avg_len
        self._exit_ema_fast = exit_ema_fast
        self._exit_ema_slow = exit_ema_slow

    @property
    def name(self) -> str:
        return "Nifty Momentum"

    @property
    def strategy_type(self) -> StrategyType:
        return "intraday"

    @property
    def params(self) -> dict[str, Any]:
        return {
            "entry_ema_fast": self._entry_ema_fast,
            "entry_ema_slow": self._entry_ema_slow,
            "candle_mult": self._candle_mult,
            "candle_avg_len": self._candle_avg_len,
            "exit_ema_fast": self._exit_ema_fast,
            "exit_ema_slow": self._exit_ema_slow,
        }

    @classmethod
    def param_space(cls) -> dict[str, list[Any]]:
        return {
            "entry_ema_fast": [13, 21],
            "entry_ema_slow": [34, 50],
            "candle_mult": [2.0, 2.5],
            "candle_avg_len": [15, 20],
            "exit_ema_fast": [3, 5, 8],
            "exit_ema_slow": [13, 21],
        }

    @classmethod
    def from_params(cls, **kwargs) -> "NiftyMomentum":
        return cls(**kwargs)

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df["entry_ema_fast"] = ema_tv(df["close"], self._entry_ema_fast)
        df["entry_ema_slow"] = ema_tv(df["close"], self._entry_ema_slow)
        df["exit_ema_fast"] = ema_tv(df["close"], self._exit_ema_fast)
        df["exit_ema_slow"] = ema_tv(df["close"], self._exit_ema_slow)
        body = abs(df["close"] - df["open"])
        df["avg_body"] = body.rolling(self._candle_avg_len).mean()
        df["body"] = body
        return df

    def compute_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.add_indicators(df)

        # --- Session boundary detection ---
        dates = pd.Series(df.index.date, index=df.index)
        session_last = dates != dates.shift(-1)
        session_force_exit = session_last.shift(-1).fillna(True)
        no_entry_zone = (
            session_last
            | session_last.shift(-1).fillna(False)
            | session_last.shift(-2).fillna(False)
            | session_last.shift(-3).fillna(False)
        )

        # --- Entry: EMA crossover + momentum candle ---
        entry_bull = df["entry_ema_fast"] > df["entry_ema_slow"]
        entry_bear = df["entry_ema_fast"] < df["entry_ema_slow"]
        entry_cross_up = entry_bull & entry_bear.shift(1).fillna(False)
        entry_cross_down = entry_bear & entry_bull.shift(1).fillna(False)

        big_bull_candle = (df["close"] > df["open"]) & (df["body"] > self._candle_mult * df["avg_body"])
        big_bear_candle = (df["close"] < df["open"]) & (df["body"] > self._candle_mult * df["avg_body"])

        df[SignalColumns.LONG_ENTRY] = (entry_cross_up & big_bull_candle & ~no_entry_zone).fillna(False)
        df[SignalColumns.SHORT_ENTRY] = (entry_cross_down & big_bear_candle & ~no_entry_zone).fillna(False)

        # --- Exit: faster EMA crossover + session close ---
        exit_bull = df["exit_ema_fast"] > df["exit_ema_slow"]
        exit_bear = df["exit_ema_fast"] < df["exit_ema_slow"]
        exit_cross_down = exit_bear & exit_bull.shift(1).fillna(False)
        exit_cross_up = exit_bull & exit_bear.shift(1).fillna(False)

        df[SignalColumns.LONG_EXIT] = (exit_cross_down | session_force_exit).fillna(False)
        df[SignalColumns.SHORT_EXIT] = (exit_cross_up | session_force_exit).fillna(False)

        return df

    def to_pine_script(self) -> str:
        header = generate_pine_header(self.name)
        return (
            f"{header}\n"
            f"// Entry Inputs\n"
            f"entryFast = input.int({self._entry_ema_fast}, 'Entry EMA Fast')\n"
            f"entrySlow = input.int({self._entry_ema_slow}, 'Entry EMA Slow')\n"
            f"candleMult = input.float({self._candle_mult}, 'Candle Body Multiplier')\n"
            f"candleAvgLen = input.int({self._candle_avg_len}, 'Candle Avg Length')\n"
            f"\n"
            f"// Exit Inputs\n"
            f"exitFast = input.int({self._exit_ema_fast}, 'Exit EMA Fast')\n"
            f"exitSlow = input.int({self._exit_ema_slow}, 'Exit EMA Slow')\n"
            f"\n"
            f"// Entry Indicators\n"
            f"entryFastEMA = ta.ema(close, entryFast)\n"
            f"entrySlowEMA = ta.ema(close, entrySlow)\n"
            f"\n"
            f"// Momentum Candle Detection\n"
            f"bodySize = math.abs(close - open)\n"
            f"avgBody = ta.sma(bodySize, candleAvgLen)\n"
            f"bigBullCandle = close > open and bodySize > candleMult * avgBody\n"
            f"bigBearCandle = close < open and bodySize > candleMult * avgBody\n"
            f"\n"
            f"// Entry Signals: EMA crossover + momentum candle\n"
            f"entryCrossUp = ta.crossover(entryFastEMA, entrySlowEMA)\n"
            f"entryCrossDown = ta.crossunder(entryFastEMA, entrySlowEMA)\n"
            f"\n"
            f"// Session filter — no entries in last 20 min\n"
            f"isNearClose = (hour == 15 and minute >= 10) or hour > 15\n"
            f"\n"
            f"longEntry = entryCrossUp and bigBullCandle and not isNearClose\n"
            f"shortEntry = entryCrossDown and bigBearCandle and not isNearClose\n"
            f"\n"
            f"// Exit Indicators (faster EMA pair)\n"
            f"exitFastEMA = ta.ema(close, exitFast)\n"
            f"exitSlowEMA = ta.ema(close, exitSlow)\n"
            f"\n"
            f"// Exit Signals: faster EMA crossover or session end\n"
            f"isForceExit = hour == 15 and minute >= 20\n"
            f"longExit = ta.crossunder(exitFastEMA, exitSlowEMA) or isForceExit\n"
            f"shortExit = ta.crossover(exitFastEMA, exitSlowEMA) or isForceExit\n"
            f"\n"
            f"// Strategy Execution\n"
            f"if longEntry\n"
            f"    strategy.entry('Long', strategy.long)\n"
            f"if longExit\n"
            f"    strategy.close('Long')\n"
            f"if shortEntry\n"
            f"    strategy.entry('Short', strategy.short)\n"
            f"if shortExit\n"
            f"    strategy.close('Short')\n"
            f"\n"
            f"// Plots\n"
            f"plot(entryFastEMA, 'Entry Fast EMA', color.blue, linewidth=2)\n"
            f"plot(entrySlowEMA, 'Entry Slow EMA', color.orange, linewidth=2)\n"
            f"plot(exitFastEMA, 'Exit Fast EMA', color.new(color.green, 60))\n"
            f"plot(exitSlowEMA, 'Exit Slow EMA', color.new(color.red, 60))\n"
        )
