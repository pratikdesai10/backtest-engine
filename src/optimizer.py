"""Grid-search optimizer with filtering and ranking."""

import itertools
from dataclasses import dataclass, field
from typing import Type

import pandas as pd

from src.config import EngineConfig, OptimizerConfig
from src.engine import BacktestEngine, BacktestResult
from src.metrics import PerformanceMetrics, calculate_metrics
from src.strategy import Strategy


@dataclass
class VariantResult:
    """Result for a single parameter variant across all assets."""
    params: dict
    per_asset: dict[str, PerformanceMetrics]
    avg_net_profit_pct: float
    avg_max_drawdown_pct: float
    avg_profit_to_drawdown: float


def generate_variants(
    strategy_cls: Type[Strategy], max_variants: int = 500
) -> list[dict]:
    """Generate parameter combinations from the strategy's param_space.

    Caps at max_variants via uniform sampling if the full grid is too large.
    """
    space = strategy_cls.param_space()
    if not space:
        return [{}]

    keys = list(space.keys())
    values = list(space.values())
    all_combos = list(itertools.product(*values))

    if len(all_combos) <= max_variants:
        return [dict(zip(keys, combo)) for combo in all_combos]

    # Uniform sampling to cap variants
    step = len(all_combos) / max_variants
    indices = [int(i * step) for i in range(max_variants)]
    return [dict(zip(keys, all_combos[i])) for i in indices]


def run_optimization(
    strategy_cls: Type[Strategy],
    datasets: dict[str, pd.DataFrame],
    engine_config: EngineConfig | None = None,
    optimizer_config: OptimizerConfig | None = None,
) -> list[VariantResult]:
    """Run backtest for each parameter variant across all assets.

    Returns filtered and ranked list of VariantResult.
    """
    engine_config = engine_config or EngineConfig()
    optimizer_config = optimizer_config or OptimizerConfig()
    engine = BacktestEngine(engine_config)

    variants = generate_variants(strategy_cls, optimizer_config.max_variants)
    results: list[VariantResult] = []

    for params in variants:
        strategy = strategy_cls.from_params(**params)
        per_asset: dict[str, PerformanceMetrics] = {}

        for asset_name, df in datasets.items():
            df_copy = df.copy()
            df_copy = strategy.compute_signals(df_copy)
            bt_result = engine.run(df_copy)
            metrics = calculate_metrics(bt_result)
            per_asset[asset_name] = metrics

        # Average metrics across assets
        if per_asset:
            avg_profit = sum(m.net_profit_pct for m in per_asset.values()) / len(per_asset)
            avg_dd = sum(m.max_drawdown_pct for m in per_asset.values()) / len(per_asset)
            avg_p2d = sum(m.profit_to_drawdown for m in per_asset.values()) / len(per_asset)
        else:
            avg_profit = avg_dd = avg_p2d = 0.0

        results.append(VariantResult(
            params=params,
            per_asset=per_asset,
            avg_net_profit_pct=avg_profit,
            avg_max_drawdown_pct=avg_dd,
            avg_profit_to_drawdown=avg_p2d,
        ))

    # Filter: discard unprofitable or excessive drawdown
    results = [
        r for r in results
        if r.avg_net_profit_pct > optimizer_config.min_net_profit_pct
        and r.avg_max_drawdown_pct <= optimizer_config.max_drawdown_pct
    ]

    # Rank by profit-to-drawdown ratio descending
    results.sort(key=lambda r: r.avg_profit_to_drawdown, reverse=True)

    return results


def print_leaderboard(results: list[VariantResult], top_n: int = 10) -> str:
    """Format a leaderboard table of top variants."""
    lines = [
        f"{'Rank':<6}{'Params':<40}{'Net Profit %':<14}{'Max DD %':<12}{'P/DD Ratio':<12}",
        "-" * 84,
    ]

    for i, r in enumerate(results[:top_n], 1):
        params_str = ", ".join(f"{k}={v}" for k, v in r.params.items())
        if len(params_str) > 37:
            params_str = params_str[:34] + "..."
        lines.append(
            f"{i:<6}{params_str:<40}{r.avg_net_profit_pct:<14.2f}"
            f"{r.avg_max_drawdown_pct:<12.2f}{r.avg_profit_to_drawdown:<12.2f}"
        )

    return "\n".join(lines)
