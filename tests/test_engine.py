"""Tests for the backtest engine."""

import numpy as np
import pandas as pd
import pytest

from src.config import EngineConfig
from src.engine import BacktestEngine, BacktestResult
from src.strategy import SignalColumns


def make_df(n=10, base_price=100.0):
    """Create a simple OHLCV DataFrame with signal columns."""
    index = pd.date_range("2024-01-01", periods=n, freq="D")
    prices = [base_price + i for i in range(n)]
    df = pd.DataFrame({
        "open": prices,
        "high": [p + 2 for p in prices],
        "low": [p - 1 for p in prices],
        "close": [p + 1 for p in prices],
    }, index=index)
    for col in [SignalColumns.LONG_ENTRY, SignalColumns.LONG_EXIT,
                SignalColumns.SHORT_ENTRY, SignalColumns.SHORT_EXIT]:
        df[col] = False
    return df


class TestNextBarExecution:
    def test_signal_fills_on_next_bar_open(self):
        """Signal on bar[i] should fill at bar[i+1] open."""
        df = make_df(5)
        df.loc[df.index[0], SignalColumns.LONG_ENTRY] = True
        df.loc[df.index[3], SignalColumns.LONG_EXIT] = True

        engine = BacktestEngine(EngineConfig(commission_pct=0.0))
        result = engine.run(df)

        assert len(result.trades) == 1
        trade = result.trades[0]
        # Entry should be at bar[1] open (next bar after signal on bar[0])
        assert trade.entry_price == df["open"].iloc[1]
        assert trade.entry_time == df.index[1]
        # Exit should be at bar[4] open (next bar after signal on bar[3])
        assert trade.exit_price == df["open"].iloc[4]
        assert trade.exit_time == df.index[4]

    def test_no_fill_same_bar_as_signal(self):
        """Should not fill on the same bar the signal fires."""
        df = make_df(3)
        df.loc[df.index[0], SignalColumns.LONG_ENTRY] = True
        df.loc[df.index[1], SignalColumns.LONG_EXIT] = True

        engine = BacktestEngine(EngineConfig(commission_pct=0.0))
        result = engine.run(df)

        # Entry on bar[1], exit signal on bar[1] but fill on bar[2]
        trade = result.trades[0]
        assert trade.entry_time == df.index[1]
        assert trade.exit_time == df.index[2]


class TestCommission:
    def test_commission_on_entry_and_exit(self):
        """Commission should be applied on both entry and exit."""
        df = make_df(5)
        df.loc[df.index[0], SignalColumns.LONG_ENTRY] = True
        df.loc[df.index[3], SignalColumns.LONG_EXIT] = True

        config = EngineConfig(initial_capital=10000, commission_pct=1.0)
        engine = BacktestEngine(config)
        result = engine.run(df)

        trade = result.trades[0]
        assert trade.commission > 0
        # Final equity should be less than if no commission
        config_no_comm = EngineConfig(initial_capital=10000, commission_pct=0.0)
        result_no_comm = BacktestEngine(config_no_comm).run(df.copy())
        assert result.final_equity < result_no_comm.final_equity


class TestPositionSizing:
    def test_position_size_percentage(self):
        """Position size should respect position_size_pct."""
        df = make_df(5)
        df.loc[df.index[0], SignalColumns.LONG_ENTRY] = True

        config = EngineConfig(
            initial_capital=10000, position_size_pct=50.0, commission_pct=0.0
        )
        engine = BacktestEngine(config)
        result = engine.run(df)

        # Force-closed trade: qty should be 50% of capital / entry price
        trade = result.trades[0]
        entry_price = df["open"].iloc[1]
        expected_qty = (10000 * 50.0 / 100.0) / entry_price
        assert trade.qty == pytest.approx(expected_qty)


class TestNoPyramiding:
    def test_ignores_entry_while_in_position(self):
        """Should not open new position while already in one."""
        df = make_df(10)
        df.loc[df.index[0], SignalColumns.LONG_ENTRY] = True
        df.loc[df.index[3], SignalColumns.LONG_ENTRY] = True  # Should be ignored
        df.loc[df.index[7], SignalColumns.LONG_EXIT] = True

        engine = BacktestEngine(EngineConfig(commission_pct=0.0))
        result = engine.run(df)

        # Only one trade should have been executed
        assert len(result.trades) == 1


class TestForceClose:
    def test_force_close_at_last_bar(self):
        """Open positions should be closed at the last bar's close."""
        df = make_df(5)
        df.loc[df.index[0], SignalColumns.LONG_ENTRY] = True
        # No exit signal

        engine = BacktestEngine(EngineConfig(commission_pct=0.0))
        result = engine.run(df)

        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.exit_price == df["close"].iloc[-1]
        assert trade.exit_time == df.index[-1]


class TestShortTrades:
    def test_short_entry_exit(self):
        """Short trades should profit from price decreases."""
        index = pd.date_range("2024-01-01", periods=5, freq="D")
        # Declining prices
        df = pd.DataFrame({
            "open":  [110, 108, 105, 102, 100],
            "high":  [112, 110, 107, 104, 102],
            "low":   [108, 106, 103, 100, 98],
            "close": [109, 106, 103, 101, 99],
        }, index=index, dtype=float)
        df[SignalColumns.LONG_ENTRY] = False
        df[SignalColumns.LONG_EXIT] = False
        df[SignalColumns.SHORT_ENTRY] = False
        df[SignalColumns.SHORT_EXIT] = False
        df.loc[index[0], SignalColumns.SHORT_ENTRY] = True
        df.loc[index[3], SignalColumns.SHORT_EXIT] = True

        engine = BacktestEngine(EngineConfig(commission_pct=0.0))
        result = engine.run(df)

        trade = result.trades[0]
        assert trade.direction == "short"
        assert trade.pnl > 0  # Price went down, short should profit


class TestEquityCurve:
    def test_equity_curve_length(self):
        """Equity curve should have same length as input data."""
        df = make_df(10)
        engine = BacktestEngine()
        result = engine.run(df)
        assert len(result.equity_curve) == len(df)

    def test_equity_curve_no_trades(self):
        """With no signals, equity should remain at initial capital."""
        df = make_df(5)
        config = EngineConfig(initial_capital=50000)
        engine = BacktestEngine(config)
        result = engine.run(df)

        assert (result.equity_curve == 50000.0).all()
        assert result.final_equity == 50000.0
