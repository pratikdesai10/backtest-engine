"""Final backtest of the optimized Nifty Momentum strategy."""

from pathlib import Path

from src.config import EngineConfig
from src.data_loader import load_csv
from src.engine import BacktestEngine
from src.metrics import calculate_metrics
from strategies.intraday.nifty_momentum import NiftyMomentum

DATA_PATH = Path("data/5min/indices/NSE_NIFTY50-INDEX.csv")

# Best parameters from grid search
BEST_PARAMS = {
    "entry_ema_fast": 21,
    "entry_ema_slow": 50,
    "candle_mult": 2.5,
    "candle_avg_len": 15,
    "exit_ema_fast": 8,
    "exit_ema_slow": 13,
}


def run_detailed_backtest(commission_pct: float):
    df = load_csv(DATA_PATH)
    config = EngineConfig(initial_capital=100_000, commission_pct=commission_pct)
    engine = BacktestEngine(config)
    strategy = NiftyMomentum.from_params(**BEST_PARAMS)

    df = strategy.compute_signals(df)
    result = engine.run(df)
    metrics = calculate_metrics(result)

    trades = result.trades
    pnls = [t.pnl - t.commission for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 1
    rr = avg_win / avg_loss

    long_trades = [t for t in trades if t.direction == "long"]
    short_trades = [t for t in trades if t.direction == "short"]
    long_wins = sum(1 for t in long_trades if t.pnl - t.commission > 0)
    short_wins = sum(1 for t in short_trades if t.pnl - t.commission > 0)

    # Trade duration stats
    durations = [(t.exit_time - t.entry_time).total_seconds() / 60 for t in trades]
    avg_duration = sum(durations) / len(durations) if durations else 0
    win_durations = [d for d, p in zip(durations, pnls) if p > 0]
    loss_durations = [d for d, p in zip(durations, pnls) if p < 0]
    avg_win_dur = sum(win_durations) / len(win_durations) if win_durations else 0
    avg_loss_dur = sum(loss_durations) / len(loss_durations) if loss_durations else 0

    # Biggest trades
    best_trade = max(trades, key=lambda t: t.pnl - t.commission) if trades else None
    worst_trade = min(trades, key=lambda t: t.pnl - t.commission) if trades else None

    # Consecutive wins/losses
    max_consec_wins = max_consec_losses = consec = 0
    prev_win = None
    for p in pnls:
        is_win = p > 0
        if is_win == prev_win:
            consec += 1
        else:
            consec = 1
        if is_win:
            max_consec_wins = max(max_consec_wins, consec)
        else:
            max_consec_losses = max(max_consec_losses, consec)
        prev_win = is_win

    # Yearly breakdown
    yearly = {}
    for t in trades:
        year = t.entry_time.year
        net = t.pnl - t.commission
        if year not in yearly:
            yearly[year] = {"count": 0, "wins": 0, "net": 0.0}
        yearly[year]["count"] += 1
        if net > 0:
            yearly[year]["wins"] += 1
        yearly[year]["net"] += net

    print(f"\n{'='*60}")
    print(f"  NIFTY MOMENTUM — FINAL BACKTEST REPORT")
    print(f"  Commission: {commission_pct}% per side")
    print(f"{'='*60}")
    print(f"  Data: {DATA_PATH}")
    print(f"  Period: {df.index[0].date()} to {df.index[-1].date()}")
    print(f"  Bars: {len(df):,}")
    print(f"  Parameters: {BEST_PARAMS}")
    print(metrics.format_report())
    print(f"  Risk/Reward Ratio:   {rr:>8.2f}")
    print(f"  Avg Winning Trade:   ${avg_win:>12,.2f}")
    print(f"  Avg Losing Trade:    ${avg_loss:>12,.2f}")
    print(f"  Long Trades:         {len(long_trades):>8d} ({long_wins} wins, {long_wins/max(len(long_trades),1)*100:.1f}%)")
    print(f"  Short Trades:        {len(short_trades):>8d} ({short_wins} wins, {short_wins/max(len(short_trades),1)*100:.1f}%)")
    print(f"  Avg Trade Duration:  {avg_duration:>8.0f} min")
    print(f"  Avg Win Duration:    {avg_win_dur:>8.0f} min")
    print(f"  Avg Loss Duration:   {avg_loss_dur:>8.0f} min")
    print(f"  Max Consec Wins:     {max_consec_wins:>8d}")
    print(f"  Max Consec Losses:   {max_consec_losses:>8d}")

    if best_trade:
        net_best = best_trade.pnl - best_trade.commission
        print(f"  Best Trade:          ${net_best:>12,.2f} ({best_trade.direction} {best_trade.entry_time.date()})")
    if worst_trade:
        net_worst = worst_trade.pnl - worst_trade.commission
        print(f"  Worst Trade:         ${net_worst:>12,.2f} ({worst_trade.direction} {worst_trade.entry_time.date()})")

    print(f"\n  --- Yearly Breakdown ---")
    print(f"  {'Year':<6} {'Trades':>7} {'Wins':>6} {'Win%':>7} {'Net P&L':>12}")
    for year in sorted(yearly.keys()):
        y = yearly[year]
        wr = y["wins"] / max(y["count"], 1) * 100
        print(f"  {year:<6} {y['count']:>7} {y['wins']:>6} {wr:>6.1f}% ${y['net']:>11,.2f}")

    print(f"{'='*60}")
    return strategy


def main():
    print("Running backtest at 0.05% commission (conservative)...")
    strategy = run_detailed_backtest(0.05)

    print("\n\nRunning backtest at 0.03% commission (discount broker)...")
    run_detailed_backtest(0.03)

    # Save Pine Script
    pine_code = strategy.to_pine_script()
    out_dir = Path("output/pine/intraday")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "nifty_momentum_best.pine"
    out_path.write_text(pine_code)
    print(f"\nPine Script saved to: {out_path}")


if __name__ == "__main__":
    main()
