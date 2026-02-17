"""MACD Crossover strategy: buy when MACD crosses above signal, sell when below."""

from typing import Any

import pandas as pd

from src.indicators import macd_tv
from src.pine_translator import generate_pine_header
from src.strategy import SignalColumns, Strategy, StrategyType


class MACDCrossover(Strategy):
    """MACD line / signal line crossover strategy."""

    def __init__(self, fast: int = 12, slow: int = 26, signal_len: int = 9):
        self._fast = fast
        self._slow = slow
        self._signal_len = signal_len

    @property
    def name(self) -> str:
        return "MACD Crossover"

    @property
    def strategy_type(self) -> StrategyType:
        return "swing"

    @property
    def params(self) -> dict[str, Any]:
        return {"fast": self._fast, "slow": self._slow, "signal_len": self._signal_len}

    @classmethod
    def param_space(cls) -> dict[str, list[Any]]:
        return {
            "fast": [8, 10, 12, 14],
            "slow": [21, 26, 30],
            "signal_len": [7, 9, 12],
        }

    @classmethod
    def from_params(cls, **kwargs) -> "MACDCrossover":
        return cls(**kwargs)

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        macd_line, signal_line, histogram = macd_tv(
            df["close"], self._fast, self._slow, self._signal_len
        )
        df["macd"] = macd_line
        df["macd_signal"] = signal_line
        df["macd_hist"] = histogram
        return df

    def compute_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.add_indicators(df)

        # Crossover: MACD crosses above signal
        cross_above = (df["macd"] > df["macd_signal"]) & (
            df["macd"].shift(1) <= df["macd_signal"].shift(1)
        )
        # Crossunder: MACD crosses below signal
        cross_below = (df["macd"] < df["macd_signal"]) & (
            df["macd"].shift(1) >= df["macd_signal"].shift(1)
        )

        df[SignalColumns.LONG_ENTRY] = cross_above.fillna(False)
        df[SignalColumns.LONG_EXIT] = cross_below.fillna(False)
        df[SignalColumns.SHORT_ENTRY] = cross_below.fillna(False)
        df[SignalColumns.SHORT_EXIT] = cross_above.fillna(False)

        return df

    def to_pine_script(self) -> str:
        header = generate_pine_header(self.name)
        return (
            f"{header}\n"
            f"fast = input.int({self._fast}, 'Fast Length')\n"
            f"slow = input.int({self._slow}, 'Slow Length')\n"
            f"signal_len = input.int({self._signal_len}, 'Signal Length')\n"
            f"\n"
            f"[macdLine, signalLine, histLine] = ta.macd(close, fast, slow, signal_len)\n"
            f"\n"
            f"longEntry = ta.crossover(macdLine, signalLine)\n"
            f"longExit = ta.crossunder(macdLine, signalLine)\n"
            f"\n"
            f"if longEntry\n"
            f"    strategy.entry('Long', strategy.long)\n"
            f"if longExit\n"
            f"    strategy.close('Long')\n"
            f"    strategy.entry('Short', strategy.short)\n"
        )
