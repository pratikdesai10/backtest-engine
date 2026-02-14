"""RSI Reversal strategy: buy when RSI crosses above oversold, sell when below overbought."""

from typing import Any

import pandas as pd

from src.indicators import rsi_tv
from src.pine_translator import generate_pine_header
from src.strategy import SignalColumns, Strategy


class RSIReversal(Strategy):
    """RSI overbought/oversold reversal strategy."""

    def __init__(self, length: int = 14, oversold: int = 30, overbought: int = 70):
        self._length = length
        self._oversold = oversold
        self._overbought = overbought

    @property
    def name(self) -> str:
        return "RSI Reversal"

    @property
    def params(self) -> dict[str, Any]:
        return {
            "length": self._length,
            "oversold": self._oversold,
            "overbought": self._overbought,
        }

    @classmethod
    def param_space(cls) -> dict[str, list[Any]]:
        return {
            "length": [7, 10, 14, 21],
            "oversold": [20, 25, 30, 35],
            "overbought": [65, 70, 75, 80],
        }

    @classmethod
    def from_params(cls, **kwargs) -> "RSIReversal":
        return cls(**kwargs)

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df["rsi"] = rsi_tv(df["close"], self._length)
        return df

    def compute_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.add_indicators(df)

        rsi = df["rsi"]
        rsi_prev = rsi.shift(1)

        # Cross above oversold → long entry
        df[SignalColumns.LONG_ENTRY] = ((rsi > self._oversold) & (rsi_prev <= self._oversold)).fillna(False)
        # Cross below overbought → long exit
        df[SignalColumns.LONG_EXIT] = ((rsi < self._overbought) & (rsi_prev >= self._overbought)).fillna(False)
        # Cross below overbought → short entry
        df[SignalColumns.SHORT_ENTRY] = df[SignalColumns.LONG_EXIT]
        # Cross above oversold → short exit
        df[SignalColumns.SHORT_EXIT] = df[SignalColumns.LONG_ENTRY]

        return df

    def to_pine_script(self) -> str:
        header = generate_pine_header(self.name)
        return (
            f"{header}\n"
            f"length = input.int({self._length}, 'RSI Length')\n"
            f"oversold = input.int({self._oversold}, 'Oversold Level')\n"
            f"overbought = input.int({self._overbought}, 'Overbought Level')\n"
            f"\n"
            f"rsiVal = ta.rsi(close, length)\n"
            f"\n"
            f"longEntry = ta.crossover(rsiVal, oversold)\n"
            f"longExit = ta.crossunder(rsiVal, overbought)\n"
            f"\n"
            f"if longEntry\n"
            f"    strategy.entry('Long', strategy.long)\n"
            f"if longExit\n"
            f"    strategy.close('Long')\n"
            f"    strategy.entry('Short', strategy.short)\n"
        )
