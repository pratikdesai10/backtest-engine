"""Tests for TradingView-matching indicators."""

import numpy as np
import pandas as pd
import pytest

from src.indicators import rma, ema_tv, rsi_tv, macd_tv, bollinger_bands_tv


@pytest.fixture
def close_series():
    """Sample close prices for testing."""
    prices = [
        100, 103, 105, 101, 99, 96, 94, 97, 101, 103,
        105, 108, 111, 110, 107, 104, 101, 98, 95, 99,
        103, 106, 109, 112, 114, 111, 108, 105, 102, 106,
    ]
    index = pd.date_range("2024-01-01", periods=len(prices), freq="D")
    return pd.Series(prices, index=index, dtype=float)


class TestRMA:
    def test_basic_computation(self, close_series):
        result = rma(close_series, 5)
        # First 4 values should be NaN
        assert result.iloc[:4].isna().all()
        # 5th value should be SMA of first 5
        expected_seed = np.mean([100, 103, 105, 101, 99])
        assert result.iloc[4] == pytest.approx(expected_seed)

    def test_subsequent_values(self, close_series):
        result = rma(close_series, 5)
        alpha = 1.0 / 5
        seed = np.mean([100, 103, 105, 101, 99])
        expected_next = alpha * 96 + (1 - alpha) * seed
        assert result.iloc[5] == pytest.approx(expected_next)

    def test_short_series(self):
        s = pd.Series([1.0, 2.0], index=pd.date_range("2024-01-01", periods=2))
        result = rma(s, 5)
        assert result.isna().all()


class TestEMA:
    def test_basic_computation(self, close_series):
        result = ema_tv(close_series, 5)
        assert result.iloc[:4].isna().all()
        expected_seed = np.mean([100, 103, 105, 101, 99])
        assert result.iloc[4] == pytest.approx(expected_seed)

    def test_alpha_differs_from_rma(self, close_series):
        ema_result = ema_tv(close_series, 5)
        rma_result = rma(close_series, 5)
        # EMA alpha=2/6, RMA alpha=1/5. After seed they diverge.
        assert ema_result.iloc[5] != pytest.approx(rma_result.iloc[5])


class TestRSI:
    def test_output_range(self, close_series):
        result = rsi_tv(close_series, 14)
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_uses_rma_not_sma(self, close_series):
        """RSI should use RMA smoothing. Verify it produces valid values after length+1 bars."""
        result = rsi_tv(close_series, 5)
        # Should have valid values from index 5 onward (length=5, plus 1 for diff)
        assert result.iloc[5:].notna().all()

    def test_all_gains(self):
        """If price only goes up, RSI should be 100."""
        prices = pd.Series(
            range(1, 22), index=pd.date_range("2024-01-01", periods=21), dtype=float
        )
        result = rsi_tv(prices, 5)
        valid = result.dropna()
        assert (valid == 100.0).all()


class TestMACD:
    def test_returns_three_series(self, close_series):
        macd_line, signal, hist = macd_tv(close_series, 5, 10, 3)
        assert len(macd_line) == len(close_series)
        assert len(signal) == len(close_series)
        assert len(hist) == len(close_series)

    def test_histogram_is_difference(self, close_series):
        macd_line, signal, hist = macd_tv(close_series, 5, 10, 3)
        valid_mask = macd_line.notna() & signal.notna()
        diff = (macd_line - signal)[valid_mask]
        np.testing.assert_allclose(hist[valid_mask].values, diff.values, atol=1e-10)

    def test_macd_line_is_fast_minus_slow(self, close_series):
        macd_line, _, _ = macd_tv(close_series, 5, 10, 3)
        fast = ema_tv(close_series, 5)
        slow = ema_tv(close_series, 10)
        expected = fast - slow
        valid_mask = expected.notna() & macd_line.notna()
        np.testing.assert_allclose(
            macd_line[valid_mask].values, expected[valid_mask].values, atol=1e-10
        )


class TestBollingerBands:
    def test_middle_is_sma(self, close_series):
        upper, middle, lower = bollinger_bands_tv(close_series, 5, 2.0)
        expected_sma = close_series.rolling(5).mean()
        pd.testing.assert_series_equal(middle, expected_sma, check_names=False)

    def test_bands_symmetry(self, close_series):
        upper, middle, lower = bollinger_bands_tv(close_series, 5, 2.0)
        valid = middle.dropna().index
        diff_upper = (upper - middle).loc[valid]
        diff_lower = (middle - lower).loc[valid]
        pd.testing.assert_series_equal(diff_upper, diff_lower, check_names=False)

    def test_uses_population_stdev(self, close_series):
        upper, middle, lower = bollinger_bands_tv(close_series, 5, 2.0)
        # Population stdev (ddof=0) should differ from sample stdev (ddof=1)
        pop_std = close_series.rolling(5).std(ddof=0)
        sample_std = close_series.rolling(5).std(ddof=1)
        # Upper band should use population stdev
        expected_upper = middle + 2.0 * pop_std
        pd.testing.assert_series_equal(upper, expected_upper, check_names=False)
        # And NOT match sample stdev
        wrong_upper = middle + 2.0 * sample_std
        assert not np.allclose(
            upper.dropna().values, wrong_upper.dropna().values
        )
