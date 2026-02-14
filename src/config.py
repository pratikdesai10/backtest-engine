from dataclasses import dataclass, field


@dataclass
class EngineConfig:
    """Configuration for the backtest engine."""
    initial_capital: float = 100_000.0
    commission_pct: float = 0.1  # percent per trade side
    slippage_ticks: float = 0.0
    position_size_pct: float = 100.0  # percent of equity to use
    pyramiding: int = 0  # 0 = no pyramiding (single position)


@dataclass
class IndicatorParams:
    """Parameters for indicator calculations."""
    rsi_length: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_length: int = 20
    bb_mult: float = 2.0


@dataclass
class OptimizerConfig:
    """Configuration for the optimization workflow."""
    max_variants: int = 500
    min_net_profit_pct: float = 0.0
    max_drawdown_pct: float = 50.0
    ranking_metric: str = "profit_to_drawdown"
