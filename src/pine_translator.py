"""Pine Script v5 generation utilities."""

from pathlib import Path


def generate_pine_header(
    strategy_name: str,
    capital: float = 100_000,
    commission: float = 0.1,
) -> str:
    """Generate the standard Pine Script v5 header with strategy declaration."""
    return (
        f'//@version=5\n'
        f'strategy("{strategy_name}", overlay=true, '
        f'initial_capital={capital:.0f}, '
        f'commission_type=strategy.commission.percent, '
        f'commission_value={commission}, '
        f'default_qty_type=strategy.percent_of_equity, '
        f'default_qty_value=100)\n'
    )


def save_pine_script(code: str, filepath: str | Path) -> Path:
    """Save Pine Script code to a file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(code)
    return filepath
