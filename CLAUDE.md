# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python backtesting engine that replicates TradingView's Strategy Tester execution model exactly — same indicator calculations (SMA-seeded RMA/EMA, population stdev), next-bar order fills, commission handling, and equity curve. Also integrates with Fyers API for fetching Indian market (NSE/BSE) OHLC data. Licensed under Apache 2.0. Requires Python >=3.10.

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Tests
.venv/bin/pytest tests/                        # all tests
.venv/bin/pytest tests/test_engine.py           # single module
.venv/bin/pytest tests/test_engine.py::test_name -v  # single test

# CLI
python main.py backtest --strategy macd_crossover --data data/NSE_SBIN-EQ.csv --pine
python main.py optimize --strategy rsi_reversal --data-dir data/ --max-variants 500
python main.py fetch -s NSE:SBIN-EQ -r D --from 2023-01-01 --to 2025-02-14
```

## Architecture

### Data Flow

CSV/Fyers API → `data_loader` → DataFrame → `strategy.compute_signals(df)` → `BacktestEngine.run(df)` → `BacktestResult` → `calculate_metrics()` → `PerformanceMetrics`

### Core Modules (`src/`)

- **`strategy.py`** — `Strategy` ABC that all strategies implement. Defines the contract: `name`, `params`, `param_space()`, `from_params()`, `add_indicators()`, `compute_signals()`, `to_pine_script()`.
- **`engine.py`** — `BacktestEngine.run(df)` processes signal columns with next-bar execution (signal on bar[i] → fill at bar[i+1] open). Returns `BacktestResult` with trades and equity curve.
- **`indicators.py`** — TradingView-exact indicator implementations: `rma()`, `ema()`, `rsi()`, `macd()`, `bollinger_bands()`, `atr()`. All use SMA-seeded initialization and TV's alpha values.
- **`config.py`** — Dataclasses: `EngineConfig` (capital, commission, position sizing), `OptimizerConfig`, `IndicatorParams`.
- **`optimizer.py`** — Grid search across `param_space()` × all datasets. Ranks by profit-to-drawdown ratio.
- **`pine_translator.py`** — Exports strategies to Pine Script v5 for TradingView.
- **`fyers_auth.py` / `fyers_data.py`** — Fyers API OAuth2 auth and OHLC data fetching with automatic date-range chunking.

### Strategy Contract

Strategies live in `strategies/` and must implement the `Strategy` ABC. Signal columns are booleans: `long_entry`, `long_exit`, `short_entry`, `short_exit`. The engine handles position management — no pyramiding by default.

### Key Design Decisions

- **Next-bar execution**: Prevents lookahead bias. Signal on bar[i] fills at bar[i+1] open price.
- **TradingView indicator parity**: Use `src/indicators.py` functions, not pandas/ta-lib equivalents. RSI uses RMA (not SMA), Bollinger uses population stdev (ddof=0).
- **Force-close**: Open positions are closed at last bar's close price.
- **Data format**: DatetimeIndex, lowercase columns: `open`, `high`, `low`, `close`, `volume`.

### Standalone Research Scripts

Root-level `.py` files (`swing_backtest.py`, `best_strategy.py`, `ema_breakout_trailing.py`, etc.) are experimental strategy research scripts, not part of the core engine.

## File Organization Rules

- **All strategy files** must go in `strategies/` directory and implement the `Strategy` ABC from `src/strategy.py`
- **All Pine Script output** must be saved to `output/pine/` directory (create directory if it doesn't exist)
