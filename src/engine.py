"""Backtest engine with next-bar execution matching TradingView's behavior."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import EngineConfig
from src.strategy import SignalColumns


@dataclass
class Trade:
    """Record of a completed trade."""
    direction: str  # "long" or "short"
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    qty: float
    pnl: float
    commission: float


@dataclass
class BacktestResult:
    """Result of a backtest run."""
    trades: list[Trade]
    equity_curve: pd.Series
    final_equity: float
    config: EngineConfig


class BacktestEngine:
    """Simulates trades with next-bar execution, matching TradingView."""

    def __init__(self, config: EngineConfig | None = None):
        self.config = config or EngineConfig()

    def run(self, df: pd.DataFrame) -> BacktestResult:
        """Run backtest on a DataFrame with pre-computed signal columns.

        Expects columns: open, high, low, close, and signal columns
        (long_entry, long_exit, short_entry, short_exit).

        Key behaviors matching TradingView:
        - Signal on bar[i] → fill at bar[i+1] open
        - Position sizing: qty = (equity * pct / 100) / fill_price
        - Commission on both entry and exit
        - No pyramiding: ignores entries while in position
        - Force-close at last bar's close
        """
        cfg = self.config
        equity = cfg.initial_capital
        position = 0.0  # qty held (positive = long, negative = short)
        entry_price = 0.0
        entry_time = None
        direction = None
        trades: list[Trade] = []
        equity_values = np.full(len(df), np.nan)

        # Signal column names
        sc = SignalColumns

        # Ensure signal columns exist with False default
        for col in [sc.LONG_ENTRY, sc.LONG_EXIT, sc.SHORT_ENTRY, sc.SHORT_EXIT]:
            if col not in df.columns:
                df[col] = False

        opens = df["open"].values
        closes = df["close"].values
        long_entry = df[sc.LONG_ENTRY].values.astype(bool)
        long_exit = df[sc.LONG_EXIT].values.astype(bool)
        short_entry = df[sc.SHORT_ENTRY].values.astype(bool)
        short_exit = df[sc.SHORT_EXIT].values.astype(bool)
        times = df.index

        pending_signal = None  # ("long_entry", "long_exit", "short_entry", "short_exit")

        for i in range(len(df)):
            fill_price = opens[i]

            # Execute pending signal from previous bar
            if pending_signal is not None:
                if pending_signal == "long_entry" and position == 0.0:
                    qty = (equity * cfg.position_size_pct / 100.0) / fill_price
                    commission = qty * fill_price * cfg.commission_pct / 100.0
                    equity -= commission
                    position = qty
                    entry_price = fill_price
                    entry_time = times[i]
                    direction = "long"

                elif pending_signal == "short_entry" and position == 0.0:
                    qty = (equity * cfg.position_size_pct / 100.0) / fill_price
                    commission = qty * fill_price * cfg.commission_pct / 100.0
                    equity -= commission
                    position = -qty
                    entry_price = fill_price
                    entry_time = times[i]
                    direction = "short"

                elif pending_signal == "long_exit" and position > 0.0:
                    qty = abs(position)
                    commission = qty * fill_price * cfg.commission_pct / 100.0
                    pnl = qty * (fill_price - entry_price)
                    equity += pnl - commission
                    trades.append(Trade(
                        direction="long",
                        entry_time=entry_time,
                        entry_price=entry_price,
                        exit_time=times[i],
                        exit_price=fill_price,
                        qty=qty,
                        pnl=pnl,
                        commission=commission,
                    ))
                    position = 0.0
                    direction = None

                elif pending_signal == "short_exit" and position < 0.0:
                    qty = abs(position)
                    commission = qty * fill_price * cfg.commission_pct / 100.0
                    pnl = qty * (entry_price - fill_price)
                    equity += pnl - commission
                    trades.append(Trade(
                        direction="short",
                        entry_time=entry_time,
                        entry_price=entry_price,
                        exit_time=times[i],
                        exit_price=fill_price,
                        qty=qty,
                        pnl=pnl,
                        commission=commission,
                    ))
                    position = 0.0
                    direction = None

                pending_signal = None

            # Compute unrealized equity for equity curve
            if position > 0:
                unrealized = position * (closes[i] - entry_price)
                equity_values[i] = equity + unrealized
            elif position < 0:
                unrealized = abs(position) * (entry_price - closes[i])
                equity_values[i] = equity + unrealized
            else:
                equity_values[i] = equity

            # Record signal for next-bar execution
            if position > 0 and long_exit[i]:
                pending_signal = "long_exit"
            elif position < 0 and short_exit[i]:
                pending_signal = "short_exit"
            elif position == 0.0 and long_entry[i]:
                pending_signal = "long_entry"
            elif position == 0.0 and short_entry[i]:
                pending_signal = "short_entry"

        # Force-close open position at last bar's close
        if position != 0.0:
            last_close = closes[-1]
            qty = abs(position)
            commission = qty * last_close * cfg.commission_pct / 100.0
            if position > 0:
                pnl = qty * (last_close - entry_price)
                trades.append(Trade(
                    direction="long",
                    entry_time=entry_time,
                    entry_price=entry_price,
                    exit_time=times[-1],
                    exit_price=last_close,
                    qty=qty,
                    pnl=pnl,
                    commission=commission,
                ))
            else:
                pnl = qty * (entry_price - last_close)
                trades.append(Trade(
                    direction="short",
                    entry_time=entry_time,
                    entry_price=entry_price,
                    exit_time=times[-1],
                    exit_price=last_close,
                    qty=qty,
                    pnl=pnl,
                    commission=commission,
                ))
            equity += pnl - commission
            equity_values[-1] = equity

        equity_curve = pd.Series(equity_values, index=df.index, name="equity")

        return BacktestResult(
            trades=trades,
            equity_curve=equity_curve,
            final_equity=equity,
            config=cfg,
        )
