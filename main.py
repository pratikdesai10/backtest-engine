"""CLI entry point for the backtesting engine."""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.config import EngineConfig, OptimizerConfig
from src.data_loader import load_csv, load_all_csvs, validate_ohlcv
from src.engine import BacktestEngine
from src.fyers_auth import (
    get_session, generate_token, save_token, load_token, get_fyers_client,
)
from src.fyers_data import fetch_historical, save_to_csv
from src.metrics import calculate_metrics
from src.optimizer import run_optimization, print_leaderboard
from src.pine_translator import save_pine_script
from strategies.macd_crossover import MACDCrossover
from strategies.rsi_reversal import RSIReversal
from strategies.bb_squeeze import BBSqueeze

STRATEGIES = {
    "macd_crossover": MACDCrossover,
    "rsi_reversal": RSIReversal,
    "bb_squeeze": BBSqueeze,
}


def cmd_backtest(args: argparse.Namespace) -> None:
    """Run a single backtest."""
    strategy_cls = STRATEGIES.get(args.strategy)
    if strategy_cls is None:
        print(f"Unknown strategy: {args.strategy}")
        print(f"Available: {', '.join(STRATEGIES.keys())}")
        sys.exit(1)

    df = load_csv(args.data)
    issues = validate_ohlcv(df)
    if issues:
        print("Data validation warnings:")
        for issue in issues:
            print(f"  - {issue}")

    config = EngineConfig(
        initial_capital=args.capital,
        commission_pct=args.commission,
    )

    strategy = strategy_cls.from_params()
    df = strategy.compute_signals(df)

    engine = BacktestEngine(config)
    result = engine.run(df)
    metrics = calculate_metrics(result)

    print(f"\nStrategy: {strategy.name}")
    print(f"Data: {args.data}")
    print(f"Params: {strategy.params}")
    print(metrics.format_report())

    if args.pine:
        pine_code = strategy.to_pine_script()
        out_path = save_pine_script(
            pine_code, Path("output") / f"{args.strategy}.pine"
        )
        print(f"\nPine Script saved to: {out_path}")


def cmd_optimize(args: argparse.Namespace) -> None:
    """Run optimization across parameter variants."""
    strategy_cls = STRATEGIES.get(args.strategy)
    if strategy_cls is None:
        print(f"Unknown strategy: {args.strategy}")
        print(f"Available: {', '.join(STRATEGIES.keys())}")
        sys.exit(1)

    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        print(f"Data directory not found: {data_dir}")
        sys.exit(1)

    datasets = load_all_csvs(data_dir)
    if not datasets:
        print(f"No CSV files found in {data_dir}")
        sys.exit(1)

    print(f"Strategy: {strategy_cls.__name__}")
    print(f"Datasets: {', '.join(datasets.keys())}")
    print(f"Running optimization...\n")

    engine_config = EngineConfig(
        initial_capital=args.capital,
        commission_pct=args.commission,
    )
    optimizer_config = OptimizerConfig(
        max_variants=args.max_variants,
    )

    results = run_optimization(
        strategy_cls, datasets, engine_config, optimizer_config
    )

    if not results:
        print("No profitable variants found.")
        sys.exit(0)

    leaderboard = print_leaderboard(results)
    print(leaderboard)

    if args.pine and results:
        best = results[0]
        strategy = strategy_cls.from_params(**best.params)
        pine_code = strategy.to_pine_script()
        out_path = save_pine_script(
            pine_code, Path("output") / f"{args.strategy}_optimized.pine"
        )
        print(f"\nBest variant Pine Script saved to: {out_path}")


def cmd_fetch(args: argparse.Namespace) -> None:
    """Fetch historical OHLC data from Fyers API."""
    load_dotenv()

    client_id = os.environ.get("FYERS_APP_ID")
    secret_key = os.environ.get("FYERS_SECRET_KEY")
    redirect_uri = os.environ.get("FYERS_REDIRECT_URI")

    if not client_id or not secret_key or not redirect_uri:
        print("Missing Fyers credentials. Set FYERS_APP_ID, FYERS_SECRET_KEY, "
              "and FYERS_REDIRECT_URI in .env file.")
        print("See .env.example for the template.")
        sys.exit(1)

    # Try to load existing token, otherwise run auth flow
    access_token = load_token()
    if access_token is None:
        session = get_session(client_id, secret_key, redirect_uri)
        auth_code = input("Enter the auth_code from the redirect URL: ").strip()
        access_token = generate_token(session, auth_code)
        save_token(access_token)
        print("Access token saved for today's session.")

    fyers_client = get_fyers_client(client_id, access_token)

    print(f"\nFetching {args.symbol} ({args.resolution}) "
          f"from {args.date_from} to {args.date_to}...")

    df = fetch_historical(
        fyers_client,
        symbol=args.symbol,
        resolution=args.resolution,
        start_date=args.date_from,
        end_date=args.date_to,
    )

    filepath = save_to_csv(df, args.symbol, args.output_dir)

    # Validate the generated CSV is compatible with the backtest engine
    issues = validate_ohlcv(df)
    if issues:
        print("\nData validation warnings:")
        for issue in issues:
            print(f"  - {issue}")

    print(f"\nFetched {len(df)} bars")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")
    print(f"Saved to: {filepath}")
    print(f"\nRun backtest with:")
    print(f"  python main.py backtest --strategy macd_crossover --data {filepath}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backtesting engine matching TradingView's Strategy Tester"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Fetch command
    fetch = subparsers.add_parser("fetch", help="Fetch OHLC data from Fyers API")
    fetch.add_argument("--symbol", "-s", required=True,
                       help="Fyers symbol (e.g. NSE:SBIN-EQ, NSE:NIFTY50-INDEX)")
    fetch.add_argument("--resolution", "-r", default="D",
                       help="Candle resolution: D, 1, 5, 15, 30, 60, 120, 240")
    fetch.add_argument("--from", dest="date_from", required=True,
                       help="Start date (yyyy-mm-dd)")
    fetch.add_argument("--to", dest="date_to", required=True,
                       help="End date (yyyy-mm-dd)")
    fetch.add_argument("--output-dir", default="data",
                       help="Output directory (default: data/)")

    # Backtest command
    bt = subparsers.add_parser("backtest", help="Run a single backtest")
    bt.add_argument("--strategy", "-s", required=True, choices=STRATEGIES.keys())
    bt.add_argument("--data", "-d", required=True, help="Path to CSV file")
    bt.add_argument("--capital", type=float, default=100_000, help="Initial capital")
    bt.add_argument("--commission", type=float, default=0.1, help="Commission %%")
    bt.add_argument("--pine", action="store_true", help="Generate Pine Script")

    # Optimize command
    opt = subparsers.add_parser("optimize", help="Run parameter optimization")
    opt.add_argument("--strategy", "-s", required=True, choices=STRATEGIES.keys())
    opt.add_argument("--data-dir", "-d", required=True, help="Directory with CSVs")
    opt.add_argument("--capital", type=float, default=100_000, help="Initial capital")
    opt.add_argument("--commission", type=float, default=0.1, help="Commission %%")
    opt.add_argument("--max-variants", type=int, default=500, help="Max variants")
    opt.add_argument("--pine", action="store_true", help="Generate Pine Script for best")

    args = parser.parse_args()

    if args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "backtest":
        cmd_backtest(args)
    elif args.command == "optimize":
        cmd_optimize(args)


if __name__ == "__main__":
    main()
