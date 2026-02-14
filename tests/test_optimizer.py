"""Tests for the optimizer module."""

from pathlib import Path

import pandas as pd
import pytest

from src.config import EngineConfig, OptimizerConfig
from src.data_loader import load_csv
from src.optimizer import generate_variants, run_optimization, print_leaderboard
from strategies.macd_crossover import MACDCrossover
from strategies.rsi_reversal import RSIReversal

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestGenerateVariants:
    def test_generates_all_combinations(self):
        variants = generate_variants(MACDCrossover, max_variants=1000)
        # 4 fast * 3 slow * 3 signal = 36
        assert len(variants) == 36

    def test_caps_at_max_variants(self):
        variants = generate_variants(RSIReversal, max_variants=10)
        assert len(variants) == 10

    def test_variant_has_correct_keys(self):
        variants = generate_variants(MACDCrossover, max_variants=5)
        for v in variants:
            assert "fast" in v
            assert "slow" in v
            assert "signal_len" in v


class TestRunOptimization:
    def test_returns_ranked_results(self):
        df = load_csv(FIXTURES_DIR / "sample_ohlcv.csv")
        datasets = {"test_asset": df}

        results = run_optimization(
            MACDCrossover,
            datasets,
            engine_config=EngineConfig(commission_pct=0.0),
            optimizer_config=OptimizerConfig(max_variants=10, min_net_profit_pct=-100),
        )

        # Should return some results
        assert isinstance(results, list)

        # If multiple results, should be sorted by profit_to_drawdown desc
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].avg_profit_to_drawdown >= results[i + 1].avg_profit_to_drawdown

    def test_filters_unprofitable(self):
        df = load_csv(FIXTURES_DIR / "sample_ohlcv.csv")
        datasets = {"test_asset": df}

        results = run_optimization(
            MACDCrossover,
            datasets,
            optimizer_config=OptimizerConfig(
                max_variants=10, min_net_profit_pct=1000
            ),
        )
        # With very high profit threshold, should filter everything
        assert len(results) == 0


class TestPrintLeaderboard:
    def test_leaderboard_format(self):
        df = load_csv(FIXTURES_DIR / "sample_ohlcv.csv")
        datasets = {"test_asset": df}

        results = run_optimization(
            MACDCrossover,
            datasets,
            optimizer_config=OptimizerConfig(max_variants=5, min_net_profit_pct=-100),
        )

        if results:
            output = print_leaderboard(results, top_n=3)
            assert "Rank" in output
            assert "Net Profit" in output
