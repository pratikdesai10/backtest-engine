"""Tests for Fyers data fetching module (mocked, no live API calls)."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.data_loader import load_csv, validate_ohlcv
from src.fyers_data import (
    _compute_chunks,
    _is_intraday,
    candles_to_dataframe,
    fetch_historical,
    sanitize_symbol,
    save_to_csv,
)


class TestIsIntraday:
    def test_minute_resolutions(self):
        for res in ["1", "2", "3", "5", "10", "15", "20", "30", "60", "120", "240"]:
            assert _is_intraday(res) is True

    def test_daily_resolution(self):
        assert _is_intraday("D") is False
        assert _is_intraday("1D") is False


class TestComputeChunks:
    def test_small_range_single_chunk(self):
        chunks = _compute_chunks("2024-01-01", "2024-02-15", chunk_days=90)
        assert len(chunks) == 1
        assert chunks[0] == ("2024-01-01", "2024-02-15")

    def test_exact_chunk_size(self):
        # 90 days: Jan 1 + 89 = Mar 30. So Jan1-Mar30 fits in one chunk.
        chunks = _compute_chunks("2024-01-01", "2024-03-30", chunk_days=90)
        assert len(chunks) == 1
        assert chunks[0] == ("2024-01-01", "2024-03-30")

    def test_one_day_over_chunk_boundary(self):
        # Jan 1 to Mar 31 = 91 days → 2 chunks
        chunks = _compute_chunks("2024-01-01", "2024-03-31", chunk_days=90)
        assert len(chunks) == 2
        assert chunks[0] == ("2024-01-01", "2024-03-30")
        assert chunks[1] == ("2024-03-31", "2024-03-31")

    def test_intraday_200_days_splits_into_3_chunks(self):
        # 200 days with 90-day chunks → 3 chunks (90 + 90 + 20)
        chunks = _compute_chunks("2024-01-01", "2024-07-18", chunk_days=90)
        assert len(chunks) == 3
        # First chunk: Jan 1 - Mar 30 (90 days)
        assert chunks[0][0] == "2024-01-01"
        # Second chunk starts Mar 31
        assert chunks[1][0] == "2024-03-31"
        # Third chunk ends at Jul 18
        assert chunks[2][1] == "2024-07-18"

    def test_daily_large_range(self):
        # 2 years with 350-day chunks → 3 chunks
        chunks = _compute_chunks("2023-01-01", "2024-12-31", chunk_days=350)
        assert len(chunks) >= 2

    def test_single_day(self):
        chunks = _compute_chunks("2024-06-15", "2024-06-15", chunk_days=90)
        assert len(chunks) == 1
        assert chunks[0] == ("2024-06-15", "2024-06-15")


class TestCandlesToDataframe:
    def test_basic_conversion(self):
        candles = [
            [1704067200, 100.0, 105.0, 99.0, 103.0, 1000],  # 2024-01-01
            [1704153600, 103.0, 107.0, 102.0, 106.0, 1200],  # 2024-01-02
            [1704240000, 106.0, 108.0, 104.0, 105.0, 1100],  # 2024-01-03
        ]
        df = candles_to_dataframe(candles)

        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert df.index.name == "time"
        assert isinstance(df.index, pd.DatetimeIndex)
        assert len(df) == 3

    def test_values_correct(self):
        candles = [[1704067200, 100.0, 105.0, 99.0, 103.0, 1000]]
        df = candles_to_dataframe(candles)

        assert df.iloc[0]["open"] == 100.0
        assert df.iloc[0]["high"] == 105.0
        assert df.iloc[0]["low"] == 99.0
        assert df.iloc[0]["close"] == 103.0
        assert df.iloc[0]["volume"] == 1000

    def test_sorted_ascending(self):
        # Pass candles in reverse order
        candles = [
            [1704240000, 106.0, 108.0, 104.0, 105.0, 1100],
            [1704067200, 100.0, 105.0, 99.0, 103.0, 1000],
        ]
        df = candles_to_dataframe(candles)
        assert df.index.is_monotonic_increasing


class TestSanitizeSymbol:
    def test_equity(self):
        assert sanitize_symbol("NSE:SBIN-EQ") == "NSE_SBIN-EQ"

    def test_index(self):
        assert sanitize_symbol("NSE:NIFTY50-INDEX") == "NSE_NIFTY50-INDEX"

    def test_no_colon(self):
        assert sanitize_symbol("SBIN") == "SBIN"


class TestSaveToCSV:
    def test_saves_compatible_csv(self, tmp_path):
        """Generated CSV should be loadable by the backtest engine's data_loader."""
        candles = [
            [1704067200, 100.0, 105.0, 99.0, 103.0, 1000],
            [1704153600, 103.0, 107.0, 102.0, 106.0, 1200],
            [1704240000, 106.0, 108.0, 104.0, 105.0, 1100],
            [1704326400, 105.0, 106.0, 100.0, 101.0, 1300],
            [1704412800, 101.0, 103.0, 98.0, 99.0, 1500],
        ]
        df = candles_to_dataframe(candles)
        filepath = save_to_csv(df, "NSE:SBIN-EQ", tmp_path)

        assert filepath.name == "NSE_SBIN-EQ.csv"
        assert filepath.exists()

        # Load with the backtest engine's data_loader
        loaded = load_csv(filepath)
        assert list(loaded.columns) == ["open", "high", "low", "close", "volume"]
        assert loaded.index.name == "time"
        assert isinstance(loaded.index, pd.DatetimeIndex)
        assert len(loaded) == 5

        # Validate passes with no issues
        issues = validate_ohlcv(loaded)
        assert issues == []


class TestFetchHistorical:
    def _make_mock_client(self, candles_per_chunk: list[list[list]]):
        """Create a mock fyers client that returns candles for each chunk call."""
        mock = MagicMock()
        mock.history.side_effect = [
            {"s": "ok", "candles": candles}
            for candles in candles_per_chunk
        ]
        return mock

    def test_single_chunk(self):
        candles = [
            [1704067200, 100.0, 105.0, 99.0, 103.0, 1000],
            [1704153600, 103.0, 107.0, 102.0, 106.0, 1200],
        ]
        mock_client = self._make_mock_client([candles])

        df = fetch_historical(mock_client, "NSE:SBIN-EQ", "D", "2024-01-01", "2024-01-02")

        assert len(df) == 2
        assert mock_client.history.call_count == 1

    def test_multiple_chunks_concatenated(self):
        chunk1 = [
            [1704067200, 100.0, 105.0, 99.0, 103.0, 1000],
            [1704153600, 103.0, 107.0, 102.0, 106.0, 1200],
        ]
        chunk2 = [
            [1704240000, 106.0, 108.0, 104.0, 105.0, 1100],
        ]
        mock_client = self._make_mock_client([chunk1, chunk2])

        # Use intraday to force chunking with 90-day windows
        # Date range > 90 days
        df = fetch_historical(mock_client, "NSE:SBIN-EQ", "15", "2024-01-01", "2024-06-01")

        assert len(df) == 3
        assert mock_client.history.call_count == 2

    def test_deduplicates_chunk_boundaries(self):
        # Same timestamp appears at end of chunk1 and start of chunk2
        chunk1 = [
            [1704067200, 100.0, 105.0, 99.0, 103.0, 1000],
            [1704153600, 103.0, 107.0, 102.0, 106.0, 1200],
        ]
        chunk2 = [
            [1704153600, 103.0, 107.0, 102.0, 106.0, 1200],  # duplicate
            [1704240000, 106.0, 108.0, 104.0, 105.0, 1100],
        ]
        mock_client = self._make_mock_client([chunk1, chunk2])

        df = fetch_historical(mock_client, "NSE:SBIN-EQ", "15", "2024-01-01", "2024-06-01")

        assert len(df) == 3  # duplicate removed

    def test_api_error_raises(self):
        mock_client = MagicMock()
        mock_client.history.return_value = {"s": "error", "message": "Invalid symbol"}

        with pytest.raises(RuntimeError, match="Fyers API error"):
            fetch_historical(mock_client, "NSE:BAD", "D", "2024-01-01", "2024-01-02")

    def test_empty_response_raises(self):
        mock_client = MagicMock()
        mock_client.history.return_value = {"s": "ok", "candles": []}

        with pytest.raises(ValueError, match="No data returned"):
            fetch_historical(mock_client, "NSE:SBIN-EQ", "D", "2024-01-01", "2024-01-02")
