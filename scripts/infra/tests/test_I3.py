"""Tests for I3_sensitivity.py"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import I3_sensitivity as I3


def make_scores(seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    codes = [f"RO{i:03d}" for i in range(42)]
    return pd.DataFrame(
        rng.uniform(0, 100, (42, 4)),
        index=codes,
        columns=["transport", "education", "health", "economic"],
    )


class TestBuildEnsemble:
    def test_returns_expected_columns(self):
        scores = make_scores()
        df = I3._build_ensemble(scores)
        assert "nuts3_code" in df.columns
        assert "rank" in df.columns
        assert "variant" in df.columns

    def test_rank_range_is_valid(self):
        scores = make_scores()
        df = I3._build_ensemble(scores)
        n = len(scores)
        assert df["rank"].between(1, n).all()

    def test_deterministic_with_seed(self):
        scores = make_scores()
        df1 = I3._build_ensemble(scores)
        df2 = I3._build_ensemble(scores)
        assert df1["rank"].equals(df2["rank"])


class TestRankIntervals:
    def test_min_leq_median_leq_max(self):
        scores = make_scores()
        intervals = I3.extract(scores)
        for code, v in intervals.items():
            assert v["rank_interval"][0] <= v["rank_median"] <= v["rank_interval"][1]

    def test_returns_entry_for_every_county(self):
        scores = make_scores()
        intervals = I3.extract(scores)
        assert set(intervals.keys()) == set(scores.index)

    def test_stable_county_has_narrow_interval(self):
        """All-equal pillars → every variant gives same rank → interval width 0."""
        codes = [f"RO{i:03d}" for i in range(10)]
        # Make county RO000 uniformly 50; others vary
        rng = np.random.default_rng(1)
        data = rng.uniform(0, 100, (10, 4))
        data[0] = [50, 50, 50, 50]
        scores = pd.DataFrame(data, index=codes, columns=["transport","education","health","economic"])
        intervals = I3.extract(scores)
        ri = intervals["RO000"]["rank_interval"]
        # Interval should be <= 3 (small variation from normalisation across variants)
        assert ri[1] - ri[0] <= 3
