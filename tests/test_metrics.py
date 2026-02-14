"""Tests for performance metrics calculation."""

import numpy as np
import pandas as pd
import pytest

from src.config import EngineConfig
from src.engine import BacktestEngine, BacktestResult, Trade
from src.metrics import PerformanceMetrics, calculate_metrics
from src.strategy import SignalColumns


def make_result(trades, equity_values, initial_capital=100000):
    """Helper to build a BacktestResult."""
    index = pd.date_range("2024-01-01", periods=len(equity_values), freq="D")
    config = EngineConfig(initial_capital=initial_capital)
    return BacktestResult(
        trades=trades,
        equity_curve=pd.Series(equity_values, index=index),
        final_equity=equity_values[-1],
        config=config,
    )


class TestMaxDrawdown:
    def test_simple_drawdown(self):
        equity = [100000, 110000, 105000, 108000, 112000]
        result = make_result([], equity)
        metrics = calculate_metrics(result)
        # Peak=110000, trough=105000, drawdown = 5000/110000 = 4.545%
        assert metrics.max_drawdown == pytest.approx(5000.0)
        assert metrics.max_drawdown_pct == pytest.approx(100 * 5000 / 110000, rel=1e-3)

    def test_no_drawdown(self):
        equity = [100000, 101000, 102000, 103000]
        result = make_result([], equity)
        metrics = calculate_metrics(result)
        assert metrics.max_drawdown == 0.0
        assert metrics.max_drawdown_pct == 0.0


class TestProfitFactor:
    def test_with_wins_and_losses(self):
        ts = pd.Timestamp("2024-01-01")
        trades = [
            Trade("long", ts, 100, ts, 110, 10, 100, 0),   # +100
            Trade("long", ts, 100, ts, 95, 10, -50, 0),    # -50
            Trade("long", ts, 100, ts, 108, 10, 80, 0),    # +80
        ]
        equity = [100000, 100100, 100050, 100130]
        result = make_result(trades, equity)
        metrics = calculate_metrics(result)
        # Gross profit = 100 + 80 = 180, gross loss = 50
        assert metrics.profit_factor == pytest.approx(180 / 50)

    def test_no_losses(self):
        ts = pd.Timestamp("2024-01-01")
        trades = [
            Trade("long", ts, 100, ts, 110, 10, 100, 0),
        ]
        equity = [100000, 100100]
        result = make_result(trades, equity)
        metrics = calculate_metrics(result)
        assert metrics.profit_factor == float("inf")


class TestWinRate:
    def test_win_rate_calculation(self):
        ts = pd.Timestamp("2024-01-01")
        trades = [
            Trade("long", ts, 100, ts, 110, 10, 100, 0),   # win
            Trade("long", ts, 100, ts, 95, 10, -50, 0),    # loss
            Trade("long", ts, 100, ts, 108, 10, 80, 0),    # win
            Trade("long", ts, 100, ts, 97, 10, -30, 0),    # loss
        ]
        equity = [100000, 100100, 100050, 100130, 100100]
        result = make_result(trades, equity)
        metrics = calculate_metrics(result)
        assert metrics.win_rate == pytest.approx(50.0)


class TestNoTrades:
    def test_zero_trades_metrics(self):
        equity = [100000, 100000, 100000]
        result = make_result([], equity)
        metrics = calculate_metrics(result)
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0
        assert metrics.profit_factor == 0.0


class TestFormatReport:
    def test_report_contains_key_fields(self):
        equity = [100000, 110000]
        ts = pd.Timestamp("2024-01-01")
        trades = [Trade("long", ts, 100, ts, 110, 100, 10000, 100)]
        result = make_result(trades, equity)
        metrics = calculate_metrics(result)
        report = metrics.format_report()
        assert "Net Profit" in report
        assert "Max Drawdown" in report
        assert "Win Rate" in report
        assert "Profit Factor" in report
