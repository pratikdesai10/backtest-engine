"""Fetch historical OHLC data from Fyers API with date-range chunking."""

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from fyers_apiv3 import fyersModel

# API limits: intraday max 100 days, daily max 365 days per request.
# Use conservative chunk sizes to stay safely within limits.
INTRADAY_CHUNK_DAYS = 90
DAILY_CHUNK_DAYS = 350

INTRADAY_RESOLUTIONS = {"1", "2", "3", "5", "10", "15", "20", "30", "60", "120", "240"}


def _is_intraday(resolution: str) -> bool:
    """Check if a resolution is intraday (minute-based)."""
    return resolution in INTRADAY_RESOLUTIONS


def _compute_chunks(
    start_date: str, end_date: str, chunk_days: int
) -> list[tuple[str, str]]:
    """Split a date range into chunks of chunk_days.

    Args:
        start_date: Start date as 'yyyy-mm-dd'.
        end_date: End date as 'yyyy-mm-dd'.
        chunk_days: Max days per chunk.

    Returns:
        List of (chunk_start, chunk_end) date strings.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    chunks = []

    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=chunk_days - 1), end)
        chunks.append((current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        current = chunk_end + timedelta(days=1)

    return chunks


def fetch_historical(
    fyers_client: fyersModel.FyersModel,
    symbol: str,
    resolution: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Fetch historical OHLC data, automatically chunking large date ranges.

    Args:
        fyers_client: Authenticated FyersModel instance.
        symbol: Fyers symbol (e.g. 'NSE:SBIN-EQ').
        resolution: Candle resolution ('D', '1', '5', '15', '60', etc.).
        start_date: Start date as 'yyyy-mm-dd'.
        end_date: End date as 'yyyy-mm-dd'.

    Returns:
        DataFrame with columns: time, open, high, low, close, volume.
    """
    chunk_days = INTRADAY_CHUNK_DAYS if _is_intraday(resolution) else DAILY_CHUNK_DAYS
    chunks = _compute_chunks(start_date, end_date, chunk_days)

    all_candles = []
    for chunk_start, chunk_end in chunks:
        data = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": "1",
            "range_from": chunk_start,
            "range_to": chunk_end,
            "cont_flag": "1",
        }
        response = fyers_client.history(data)

        if response.get("s") != "ok":
            raise RuntimeError(
                f"Fyers API error for {symbol} [{chunk_start} to {chunk_end}]: "
                f"{response.get('message', response)}"
            )

        candles = response.get("candles", [])
        all_candles.extend(candles)

    if not all_candles:
        raise ValueError(f"No data returned for {symbol} from {start_date} to {end_date}")

    df = candles_to_dataframe(all_candles)

    # Drop duplicate timestamps that may occur at chunk boundaries
    df = df[~df.index.duplicated(keep="first")]

    return df


def candles_to_dataframe(candles: list[list]) -> pd.DataFrame:
    """Convert raw Fyers candles array to a backtest-engine-compatible DataFrame.

    Each candle is [epoch_timestamp, open, high, low, close, volume].

    Returns DataFrame with DatetimeIndex named 'time' and lowercase columns.
    """
    df = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("time")
    df = df.sort_index()
    return df


def sanitize_symbol(symbol: str) -> str:
    """Convert a Fyers symbol to a safe filename.

    'NSE:SBIN-EQ' → 'NSE_SBIN-EQ'
    """
    return symbol.replace(":", "_")


def save_to_csv(df: pd.DataFrame, symbol: str, data_dir: str | Path = "data") -> Path:
    """Save DataFrame as a CSV compatible with backtest engine's data_loader.

    Output format:
        time,open,high,low,close,volume
        2024-01-01,100.0,105.0,99.0,103.0,1000
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{sanitize_symbol(symbol)}.csv"
    filepath = data_dir / filename

    df.to_csv(filepath, index=True)
    return filepath
