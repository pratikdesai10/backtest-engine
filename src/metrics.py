"""Performance metrics matching TradingView's Strategy Tester KPIs."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.engine import BacktestResult, Trade


@dataclass
class PerformanceMetrics:
    """Summary performance metrics for a backtest."""
    net_profit: float
    net_profit_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    profit_to_drawdown: float

    def format_report(self) -> str:
        """Human-readable performance report."""
        lines = [
            "=" * 50,
            "  BACKTEST PERFORMANCE REPORT",
            "=" * 50,
            f"  Net Profit:          ${self.net_profit:>12,.2f} ({self.net_profit_pct:>+.2f}%)",
            f"  Max Drawdown:        ${self.max_drawdown:>12,.2f} ({self.max_drawdown_pct:>-.2f}%)",
            f"  Total Trades:        {self.total_trades:>8d}",
            f"  Winning Trades:      {self.winning_trades:>8d}",
            f"  Losing Trades:       {self.losing_trades:>8d}",
            f"  Win Rate:            {self.win_rate:>8.1f}%",
            f"  Profit Factor:       {self.profit_factor:>8.2f}",
            f"  Sharpe Ratio:        {self.sharpe_ratio:>8.2f}",
            f"  Profit/Drawdown:     {self.profit_to_drawdown:>8.2f}",
            "=" * 50,
        ]
        return "\n".join(lines)


def calculate_metrics(result: BacktestResult) -> PerformanceMetrics:
    """Calculate performance metrics from a backtest result."""
    initial = result.config.initial_capital
    final = result.final_equity
    trades = result.trades
    equity = result.equity_curve

    # Net profit
    net_profit = final - initial
    net_profit_pct = (net_profit / initial) * 100.0

    # Max drawdown from equity curve
    running_max = equity.cummax()
    drawdown = equity - running_max
    drawdown_pct = (drawdown / running_max) * 100.0
    max_drawdown = drawdown.min()
    max_drawdown_pct = drawdown_pct.min()

    # Trade statistics
    total_trades = len(trades)
    if total_trades == 0:
        return PerformanceMetrics(
            net_profit=net_profit,
            net_profit_pct=net_profit_pct,
            max_drawdown=abs(max_drawdown),
            max_drawdown_pct=abs(max_drawdown_pct),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            sharpe_ratio=0.0,
            profit_to_drawdown=0.0,
        )

    # Compute net PnL per trade (pnl - commission)
    trade_pnls = [t.pnl - t.commission for t in trades]
    winning = [p for p in trade_pnls if p > 0]
    losing = [p for p in trade_pnls if p <= 0]

    winning_trades = len(winning)
    losing_trades = len(losing)
    win_rate = (winning_trades / total_trades) * 100.0

    # Profit factor: gross profit / gross loss
    gross_profit = sum(winning) if winning else 0.0
    gross_loss = abs(sum(losing)) if losing else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Sharpe ratio (annualized, assuming daily returns)
    returns = equity.pct_change().dropna()
    if len(returns) > 1 and returns.std() > 0:
        sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)
    else:
        sharpe_ratio = 0.0

    # Profit to drawdown ratio
    dd_abs = abs(max_drawdown_pct) if max_drawdown_pct != 0 else 1e-10
    profit_to_drawdown = net_profit_pct / dd_abs

    return PerformanceMetrics(
        net_profit=net_profit,
        net_profit_pct=net_profit_pct,
        max_drawdown=abs(max_drawdown),
        max_drawdown_pct=abs(max_drawdown_pct),
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate,
        profit_factor=profit_factor,
        sharpe_ratio=sharpe_ratio,
        profit_to_drawdown=profit_to_drawdown,
    )
