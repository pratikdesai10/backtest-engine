"""Strategy base class for the backtesting engine."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd


@dataclass
class SignalColumns:
    """Standard signal column names used by the engine."""
    LONG_ENTRY = "long_entry"
    LONG_EXIT = "long_exit"
    SHORT_ENTRY = "short_entry"
    SHORT_EXIT = "short_exit"


StrategyType = Literal["swing", "intraday"]


class Strategy(ABC):
    """Abstract base class for trading strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name."""

    @property
    @abstractmethod
    def strategy_type(self) -> StrategyType:
        """Strategy type: 'swing' or 'intraday'."""

    @property
    @abstractmethod
    def params(self) -> dict[str, Any]:
        """Current parameter values."""

    @classmethod
    @abstractmethod
    def param_space(cls) -> dict[str, list[Any]]:
        """Parameter grid for optimization.

        Returns a dict mapping parameter name to list of values to test.
        Example: {"rsi_length": [10, 14, 20], "oversold": [25, 30, 35]}
        """

    @classmethod
    @abstractmethod
    def from_params(cls, **kwargs) -> "Strategy":
        """Construct a strategy instance from parameter values."""

    @abstractmethod
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add indicator columns to the DataFrame. Returns modified df."""

    @abstractmethod
    def compute_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add signal columns (long_entry, long_exit, etc.) to the DataFrame.

        Should call add_indicators first, then compute boolean signal columns.
        Returns modified df.
        """

    @abstractmethod
    def to_pine_script(self) -> str:
        """Generate Pine Script v5 code for this strategy with current params."""
