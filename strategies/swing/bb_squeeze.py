"""Bollinger Band Squeeze strategy: buy above lower band, sell below upper band."""

from typing import Any

import pandas as pd

from src.indicators import bollinger_bands_tv
from src.pine_translator import generate_pine_header
from src.strategy import SignalColumns, Strategy, StrategyType


class BBSqueeze(Strategy):
    """Bollinger Band squeeze / mean-reversion strategy."""

    def __init__(self, length: int = 20, mult: float = 2.0):
        self._length = length
        self._mult = mult

    @property
    def name(self) -> str:
        return "BB Squeeze"

    @property
    def strategy_type(self) -> StrategyType:
        return "swing"

    @property
    def params(self) -> dict[str, Any]:
        return {"length": self._length, "mult": self._mult}

    @classmethod
    def param_space(cls) -> dict[str, list[Any]]:
        return {
            "length": [15, 20, 25, 30],
            "mult": [1.5, 2.0, 2.5, 3.0],
        }

    @classmethod
    def from_params(cls, **kwargs) -> "BBSqueeze":
        return cls(**kwargs)

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        upper, middle, lower = bollinger_bands_tv(
            df["close"], self._length, self._mult
        )
        df["bb_upper"] = upper
        df["bb_middle"] = middle
        df["bb_lower"] = lower
        return df

    def compute_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.add_indicators(df)

        close = df["close"]
        close_prev = close.shift(1)

        # Price crosses above lower band → long entry
        df[SignalColumns.LONG_ENTRY] = (
            (close > df["bb_lower"]) & (close_prev <= df["bb_lower"].shift(1))
        ).fillna(False)

        # Price crosses below upper band → long exit
        df[SignalColumns.LONG_EXIT] = (
            (close < df["bb_upper"]) & (close_prev >= df["bb_upper"].shift(1))
        ).fillna(False)

        # Price crosses below upper band → short entry
        df[SignalColumns.SHORT_ENTRY] = df[SignalColumns.LONG_EXIT]

        # Price crosses above lower band → short exit
        df[SignalColumns.SHORT_EXIT] = df[SignalColumns.LONG_ENTRY]

        return df

    def to_pine_script(self) -> str:
        header = generate_pine_header(self.name)
        return (
            f"{header}\n"
            f"length = input.int({self._length}, 'BB Length')\n"
            f"mult = input.float({self._mult}, 'BB Multiplier')\n"
            f"\n"
            f"[middle, upper, lower] = ta.bb(close, length, mult)\n"
            f"\n"
            f"longEntry = ta.crossover(close, lower)\n"
            f"longExit = ta.crossunder(close, upper)\n"
            f"\n"
            f"if longEntry\n"
            f"    strategy.entry('Long', strategy.long)\n"
            f"if longExit\n"
            f"    strategy.close('Long')\n"
            f"    strategy.entry('Short', strategy.short)\n"
        )
