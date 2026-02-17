# backtest-engine

## Project Overview
`backtest-engine` is a Python-based backtesting framework designed to strictly replicate the execution behavior of TradingView's Strategy Tester. It prevents lookahead bias by enforcing next-bar execution (signals on bar `i` are filled at bar `i+1` open) and provides indicator implementations that match TradingView's specific algorithms (e.g., RMA, SMA-seeded EMA, population stdev).

The project also includes robust integration with the Fyers API for fetching historical OHLC data for Indian markets (NSE/BSE).

## Building and Running

### Prerequisites
- Python >= 3.10
- Fyers API credentials (for data fetching)

### Setup
1.  **Create and activate a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

2.  **Install dependencies:**
    ```bash
    pip install -e ".[dev]"
    ```

3.  **Environment Variables:**
    Copy `.env.example` to `.env` and populate your Fyers API credentials if you intend to fetch data.
    ```bash
    cp .env.example .env
    ```

### CLI Commands

The project uses `main.py` as the primary entry point.

**1. Run a Single Backtest:**
```bash
python main.py backtest --strategy macd_crossover --data data/NSE_SBIN-EQ.csv --pine
```
*   `--strategy`: Name of the strategy (registered in `main.py`).
*   `--data`: Path to the OHLCV CSV file.
*   `--pine`: (Optional) Generate the corresponding Pine Script.

**2. Optimize a Strategy:**
Runs a grid search over the strategy's parameter space.
```bash
python main.py optimize --strategy rsi_reversal --data-dir data/ --max-variants 500
```
*   `--data-dir`: Directory containing multiple CSV files to test against.

**3. Fetch Data (Single Symbol):**
```bash
python main.py fetch -s NSE:SBIN-EQ -r D --from 2023-01-01 --to 2025-02-14
```

### Bulk Data Fetching
Use `fetch_market_data.py` for robust bulk downloading with automatic batching and retry logic.

```bash
# Fetch Nifty 50 stocks (Daily)
python fetch_market_data.py --list nifty50 --from 2023-01-01 --to 2025-02-14 --resolution D

# Fetch Nifty 500 stocks (Daily)
python fetch_market_data.py --list nifty500 --from 2024-01-01 --to 2025-02-14 --resolution D

# Fetch Indices (15min)
python fetch_market_data.py --list indices --from 2023-01-01 --to 2025-02-14 --resolution 15
```

Data is stored in `data/{resolution}/{list_type}/` (e.g., `data/daily/nifty50/`).

### Testing
Run the test suite using `pytest`:
```bash
.venv/bin/pytest tests/                        # all tests
.venv/bin/pytest tests/test_engine.py           # single module
.venv/bin/pytest tests/test_engine.py::test_name -v  # single test
```

## Architecture

### Data Flow
1.  **Input**: CSV/Fyers API → `data_loader` → `pd.DataFrame`.
2.  **Processing**: `Strategy.compute_signals(df)` calculates indicators and logic, appending `long_entry`, `long_exit`, `short_entry`, `short_exit` columns.
3.  **Execution**: `BacktestEngine.run(df)` processes signal columns with next-bar execution (signal on bar `i` → fill at bar `i+1` open).
4.  **Output**: `BacktestResult` object containing trades, equity curve, and metrics → `calculate_metrics()` → `PerformanceMetrics`.

### Core Modules (`src/`)
*   **`engine.py`**: `BacktestEngine`. Implements the core simulation loop with next-bar execution logic, commission handling, and PnL tracking.
*   **`strategy.py`**: Defines the `Strategy` abstract base class. All user strategies must inherit from this.
*   **`indicators.py`**: TradingView-exact indicator implementations: `rma()`, `ema()`, `rsi()`, `macd()`, `bollinger_bands()`, `atr()`. Uses SMA-seeded initialization and TV's alpha values.
*   **`optimizer.py`**: Grid search across `param_space()` × all datasets. Ranks by profit-to-drawdown ratio.
*   **`pine_translator.py`**: Exports strategies to Pine Script v5 for TradingView.
*   **`config.py`**: Dataclasses: `EngineConfig`, `OptimizerConfig`, `IndicatorParams`.
*   **`fyers_auth.py` / `fyers_data.py`**: Fyers API OAuth2 auth and OHLC data fetching with automatic date-range chunking.

### Key Design Decisions
*   **Next-bar execution**: Prevents lookahead bias. Signal on bar `i` fills at bar `i+1` open price.
*   **TradingView indicator parity**: Uses `src/indicators.py` functions, not pandas/ta-lib equivalents. RSI uses RMA (not SMA), Bollinger uses population stdev (ddof=0).
*   **Force-close**: Open positions are closed at last bar's close price.
*   **Data format**: DatetimeIndex, lowercase columns: `open`, `high`, `low`, `close`, `volume`.
*   **Position Management**: No pyramiding by default.

## Development Rules & Conventions

> **Note:** This file (`GEMINI.md`) must be kept in sync with `CLAUDE.md`. Any updates to project rules, architectural decisions, or workflows in `CLAUDE.md` should be immediately reflected here.

### Strategy Implementation
Strategies live in `strategies/{swing|intraday}/` and must implement the `Strategy` ABC.

**Required Methods/Properties:**
*   `name`: Human-readable strategy name.
*   `strategy_type`: Either `"swing"` or `"intraday"` (determines file organization).
*   `params`: Current parameter values as dict.
*   `param_space()`: Class method defining the optimization grid.
*   `from_params(**kwargs)`: Factory method to construct from parameters.
*   `add_indicators(df)`: Add indicator columns to DataFrame.
*   `compute_signals(df)`: Add signal columns: `long_entry`, `long_exit`, `short_entry`, `short_exit` (booleans).
*   `to_pine_script()`: Generate Pine Script v5 code.

### File Organization Rules
1.  **Strategy Files**:
    *   **Swing strategies**: `strategies/swing/` with `strategy_type = "swing"`.
    *   **Intraday strategies**: `strategies/intraday/` with `strategy_type = "intraday"`.
2.  **Pine Script Output**:
    *   **Only save the best version** after running optimization.
    *   **Swing**: `output/pine/swing/{strategy_name}_best.pine`.
    *   **Intraday**: `output/pine/intraday/{strategy_name}_best.pine`.
    *   **Never** save Pine Scripts from single backtest runs unless explicitly finding optimal parameters.

### Workflow
1.  Develop strategy in appropriate `strategies/{swing|intraday}/` directory.
2.  Run `optimize` command to find best parameters across all datasets.
3.  Best variant is automatically saved to `output/pine/{swing|intraday}/{strategy}_best.pine`.
4.  Import the `_best.pine` file to TradingView for live testing.

### Standalone Research Scripts
Root-level `.py` files (e.g., `swing_backtest.py`, `best_strategy.py`) are experimental strategy research scripts and are **not** part of the core engine.