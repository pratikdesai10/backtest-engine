from pathlib import Path

import pandas as pd


def load_csv(filepath: str | Path) -> pd.DataFrame:
    """Load a TradingView CSV export and normalize it.

    Handles varying column capitalization from TV exports.
    Returns a DataFrame with lowercase columns and a DatetimeIndex sorted ascending.
    """
    filepath = Path(filepath)
    df = pd.read_csv(filepath)

    # Normalize column names to lowercase and strip whitespace
    df.columns = df.columns.str.strip().str.lower()

    # Detect and parse the date/time column
    date_col = None
    for candidate in ["time", "date", "datetime", "timestamp"]:
        if candidate in df.columns:
            date_col = candidate
            break

    if date_col is None:
        raise ValueError(
            f"No date/time column found in {filepath}. "
            f"Expected one of: time, date, datetime, timestamp. "
            f"Got: {list(df.columns)}"
        )

    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col)
    df.index.name = "time"

    # Sort ascending by time
    df = df.sort_index()

    # Rename common TV column variations
    rename_map = {}
    for col in df.columns:
        if col in ("o", "open"):
            rename_map[col] = "open"
        elif col in ("h", "high"):
            rename_map[col] = "high"
        elif col in ("l", "low"):
            rename_map[col] = "low"
        elif col in ("c", "close"):
            rename_map[col] = "close"
        elif col in ("v", "vol", "volume"):
            rename_map[col] = "volume"
    df = df.rename(columns=rename_map)

    return df


def load_all_csvs(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Load all CSV files from a directory.

    Returns a dict mapping filename (without extension) to DataFrame.
    """
    data_dir = Path(data_dir)
    datasets = {}
    for csv_path in sorted(data_dir.glob("*.csv")):
        name = csv_path.stem
        datasets[name] = load_csv(csv_path)
    return datasets


def validate_ohlcv(df: pd.DataFrame) -> list[str]:
    """Validate OHLCV data, returning a list of issues found."""
    issues = []

    required = ["open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        issues.append(f"Missing columns: {missing}")
        return issues  # Can't do further checks without columns

    # Check for NaN values
    for col in required:
        nan_count = df[col].isna().sum()
        if nan_count > 0:
            issues.append(f"Column '{col}' has {nan_count} NaN values")

    # Check high >= low
    bad_hl = (df["high"] < df["low"]).sum()
    if bad_hl > 0:
        issues.append(f"{bad_hl} bars where high < low")

    # Check monotonic dates
    if not df.index.is_monotonic_increasing:
        issues.append("Date index is not monotonically increasing")

    return issues
