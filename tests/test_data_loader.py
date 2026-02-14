"""Tests for CSV data loading and validation."""

from pathlib import Path

import pandas as pd
import pytest

from src.data_loader import load_csv, load_all_csvs, validate_ohlcv

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestLoadCSV:
    def test_load_sample_csv(self):
        df = load_csv(FIXTURES_DIR / "sample_ohlcv.csv")
        assert isinstance(df, pd.DataFrame)
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns
        assert isinstance(df.index, pd.DatetimeIndex)
        assert df.index.name == "time"

    def test_sorted_ascending(self):
        df = load_csv(FIXTURES_DIR / "sample_ohlcv.csv")
        assert df.index.is_monotonic_increasing

    def test_column_normalization(self, tmp_path):
        """Should handle uppercase column names."""
        csv_path = tmp_path / "test.csv"
        csv_path.write_text(
            "Time,Open,High,Low,Close,Volume\n"
            "2024-01-01,100,105,99,103,1000\n"
            "2024-01-02,103,107,102,106,1200\n"
        )
        df = load_csv(csv_path)
        assert "open" in df.columns
        assert "close" in df.columns

    def test_missing_date_column_raises(self, tmp_path):
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("foo,bar\n1,2\n")
        with pytest.raises(ValueError, match="No date/time column"):
            load_csv(csv_path)


class TestLoadAllCSVs:
    def test_loads_from_directory(self):
        datasets = load_all_csvs(FIXTURES_DIR)
        assert "sample_ohlcv" in datasets
        assert isinstance(datasets["sample_ohlcv"], pd.DataFrame)

    def test_empty_directory(self, tmp_path):
        datasets = load_all_csvs(tmp_path)
        assert datasets == {}


class TestValidateOHLCV:
    def test_valid_data(self):
        df = load_csv(FIXTURES_DIR / "sample_ohlcv.csv")
        issues = validate_ohlcv(df)
        assert issues == []

    def test_missing_columns(self):
        df = pd.DataFrame({"foo": [1, 2]})
        issues = validate_ohlcv(df)
        assert any("Missing columns" in i for i in issues)

    def test_nan_values(self):
        df = pd.DataFrame({
            "open": [100, None],
            "high": [105, 107],
            "low": [99, 102],
            "close": [103, 106],
        }, index=pd.date_range("2024-01-01", periods=2))
        issues = validate_ohlcv(df)
        assert any("NaN" in i for i in issues)

    def test_high_less_than_low(self):
        df = pd.DataFrame({
            "open": [100, 103],
            "high": [105, 100],  # second bar: high < low
            "low": [99, 102],
            "close": [103, 101],
        }, index=pd.date_range("2024-01-01", periods=2))
        issues = validate_ohlcv(df)
        assert any("high < low" in i for i in issues)
