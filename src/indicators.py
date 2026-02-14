"""Indicators matching TradingView's built-in functions exactly.

All implementations use SMA-seeded initialization and the same alpha values
as TradingView/Pine Script to ensure results match within floating-point precision.
"""

import numpy as np
import pandas as pd


def rma(series: pd.Series, length: int) -> pd.Series:
    """Wilder's Moving Average (RMA), matching TradingView's ta.rma().

    alpha = 1 / length
    First value is SMA of first `length` values.
    Subsequent: rma[i] = alpha * src[i] + (1 - alpha) * rma[i-1]
    """
    values = series.values.astype(float)
    result = np.full_like(values, np.nan)
    alpha = 1.0 / length

    if len(values) < length:
        return pd.Series(result, index=series.index)

    # Seed with SMA
    result[length - 1] = np.mean(values[:length])

    # Recursive calculation
    for i in range(length, len(values)):
        result[i] = alpha * values[i] + (1.0 - alpha) * result[i - 1]

    return pd.Series(result, index=series.index)


def ema_tv(series: pd.Series, length: int) -> pd.Series:
    """EMA matching TradingView's ta.ema().

    alpha = 2 / (length + 1)
    First value is SMA of first `length` values.
    Subsequent: ema[i] = alpha * src[i] + (1 - alpha) * ema[i-1]
    """
    values = series.values.astype(float)
    result = np.full_like(values, np.nan)
    alpha = 2.0 / (length + 1)

    if len(values) < length:
        return pd.Series(result, index=series.index)

    # Seed with SMA
    result[length - 1] = np.mean(values[:length])

    # Recursive calculation
    for i in range(length, len(values)):
        result[i] = alpha * values[i] + (1.0 - alpha) * result[i - 1]

    return pd.Series(result, index=series.index)


def rsi_tv(close: pd.Series, length: int = 14) -> pd.Series:
    """RSI matching TradingView's ta.rsi().

    Uses RMA (Wilder's smoothing) for average gain and average loss,
    NOT SMA like ta-lib. This is the key difference for TV matching.
    """
    delta = close.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = rma(gain, length)
    avg_loss = rma(loss, length)

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Handle division by zero (avg_loss == 0 → RSI = 100)
    rsi = rsi.where(avg_loss != 0, 100.0)
    # Where avg_gain == 0 and avg_loss == 0, RSI is undefined but TV shows 50...
    # Actually TV would show 100 when loss=0. Keep as is.

    return rsi


def macd_tv(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal_len: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD matching TradingView's ta.macd().

    Returns (macd_line, signal_line, histogram).
    """
    fast_ema = ema_tv(close, fast)
    slow_ema = ema_tv(close, slow)

    macd_line = fast_ema - slow_ema

    # Signal is EMA of the MACD line, but only from where MACD has valid values
    # We need to compute EMA on the non-NaN portion
    valid_start = macd_line.first_valid_index()
    if valid_start is None:
        nan_series = pd.Series(np.nan, index=close.index)
        return nan_series, nan_series.copy(), nan_series.copy()

    macd_valid = macd_line.loc[valid_start:]
    signal_valid = ema_tv(macd_valid, signal_len)

    signal_line = pd.Series(np.nan, index=close.index)
    signal_line.loc[signal_valid.index] = signal_valid

    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def bollinger_bands_tv(
    close: pd.Series, length: int = 20, mult: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands matching TradingView's ta.bb().

    Uses SMA for the basis and population stdev (ddof=0), NOT sample stdev.
    Returns (upper, middle, lower).
    """
    middle = close.rolling(window=length).mean()
    stdev = close.rolling(window=length).std(ddof=0)

    upper = middle + mult * stdev
    lower = middle - mult * stdev

    return upper, middle, lower
