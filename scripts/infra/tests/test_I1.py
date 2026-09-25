"""Tests for I1_score_counties.py"""
import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import I1_score_counties as I1


class TestWinsorizeMinmax:
    def test_output_between_0_and_100(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        result = I1._winsorize_minmax(s)
        assert result.min() >= 0
        assert result.max() <= 100

    def test_all_equal_returns_50(self):
        s = pd.Series([5.0] * 10)
        result = I1._winsorize_minmax(s)
        assert (result == 50.0).all()

    def test_monotone(self):
        s = pd.Series(range(20), dtype=float)
        result = I1._winsorize_minmax(s)
        assert (result.diff().dropna() >= 0).all()


class TestGeometricMean:
    def test_equal_scores_returns_score(self):
        row = pd.Series([60.0, 60.0, 60.0, 60.0])
        assert I1._geometric_mean(row) == pytest.approx(60.0, rel=1e-4)

    def test_geom_leq_arith(self):
        row = pd.Series([10.0, 90.0, 50.0, 70.0])
        assert I1._geometric_mean(row) <= row.mean()

    def test_handles_zero_with_floor(self):
        row = pd.Series([0.0, 80.0, 60.0, 40.0])
        result = I1._geometric_mean(row)
        assert math.isfinite(result) and result > 0


class TestCronbachAlpha:
    def test_perfect_internal_consistency(self):
        # All columns identical → perfect correlation → alpha ≈ 1
        df = pd.DataFrame({"a": [1,2,3,4,5], "b": [1,2,3,4,5]})
        assert I1._cronbach_alpha(df) == pytest.approx(1.0, abs=1e-6)

    def test_uncorrelated_columns(self):
        rng = np.random.default_rng(42)
        df = pd.DataFrame(rng.standard_normal((50, 4)), columns=["a","b","c","d"])
        alpha = I1._cronbach_alpha(df)
        assert alpha < 0.5  # low internal consistency expected for random data


class TestConfidence:
    def test_high_density_is_high(self):
        # 20 features in 100 km² → density 0.2 → "high"
        assert I1._data_confidence(20, 100.0) == "high"

    def test_zero_features_is_low(self):
        assert I1._data_confidence(0, 500.0) == "low"

    def test_moderate_is_medium(self):
        assert I1._data_confidence(2, 400.0) == "medium"


class TestFindPeers:
    def test_returns_n_nearest(self):
        matrix = pd.DataFrame({
            "t": [80, 20, 75, 50],
            "e": [70, 10, 72, 40],
            "h": [60, 30, 65, 55],
            "ec": [50, 90, 55, 45],
        }, index=["A", "B", "C", "D"])
        peers = I1._find_peers("A", matrix, n=2)
        assert "C" in peers          # nearest neighbour
        assert "A" not in peers      # not self
        assert len(peers) == 2


class TestRawIntensity:
    def test_area_normalisation_scales_with_area(self):
        counts = pd.Series({"A": 100, "B": 50})
        area = pd.Series({"A": 200.0, "B": 100.0})
        pop = pd.Series({"A": 5000.0, "B": 2500.0})
        result = I1._raw_intensity(counts, area, pop, "area")
        # Both should give same density: 100/200 == 50/100 == 0.5
        assert result["A"] == pytest.approx(result["B"], rel=1e-6)

    def test_pop_normalisation_per_1k(self):
        counts = pd.Series({"A": 10, "B": 5})
        area = pd.Series({"A": 100.0, "B": 100.0})
        pop = pd.Series({"A": 2000.0, "B": 1000.0})
        result = I1._raw_intensity(counts, area, pop, "pop_1k")
        # 10/(2000/1000) = 5.0 and 5/(1000/1000) = 5.0 → same intensity
        assert result["A"] == pytest.approx(result["B"], rel=1e-6)

    def test_zero_count_returns_zero(self):
        counts = pd.Series({"A": 0, "B": 10})
        area = pd.Series({"A": 100.0, "B": 100.0})
        pop = pd.Series({"A": 1000.0, "B": 1000.0})
        result = I1._raw_intensity(counts, area, pop, "area")
        assert result["A"] == 0.0


class TestPcaWeights:
    def test_weights_sum_to_one(self):
        rng = np.random.default_rng(42)
        df = pd.DataFrame(rng.uniform(0, 100, (42, 4)), columns=["t", "e", "h", "ec"])
        weights = I1._pca_weights(df)
        assert weights.sum() == pytest.approx(1.0, abs=1e-6)

    def test_weights_are_positive(self):
        rng = np.random.default_rng(42)
        df = pd.DataFrame(rng.uniform(0, 100, (42, 4)), columns=["t", "e", "h", "ec"])
        weights = I1._pca_weights(df)
        assert (weights > 0).all()

    def test_highly_correlated_pillar_gets_high_weight(self):
        # Build data where column 0 is a near-pure signal and other columns
        # are the same signal buried in large noise.  After StandardScaler all
        # columns have unit variance, but column 0 has the highest signal-to-
        # noise ratio so its first-PC loading dominates.
        rng = np.random.default_rng(0)
        n = 200  # more rows → stable eigenvector
        signal = rng.uniform(0, 100, n)
        col0 = signal + rng.uniform(0, 0.01, n)     # near-pure signal
        col1 = signal + rng.uniform(0, 50, n)       # heavy noise
        col2 = signal + rng.uniform(0, 50, n)
        col3 = signal + rng.uniform(0, 50, n)
        df = pd.DataFrame(
            np.column_stack([col0, col1, col2, col3]),
            columns=["dom", "a", "b", "c"]
        )
        weights = I1._pca_weights(df)
        assert weights[0] == weights.max()  # dominant pillar gets highest weight


class TestNationalPercentile:
    def test_lowest_county_is_zero(self):
        scores = pd.Series({"A": 10.0, "B": 50.0, "C": 90.0})
        assert I1._national_percentile("A", scores) == 0

    def test_highest_county_is_less_than_100(self):
        scores = pd.Series({"A": 10.0, "B": 50.0, "C": 90.0})
        p = I1._national_percentile("C", scores)
        assert p == int(round(2/3 * 100))  # 2 counties below, 3 total

    def test_percentile_monotone_with_score(self):
        scores = pd.Series({"A": 10.0, "B": 50.0, "C": 90.0})
        pa = I1._national_percentile("A", scores)
        pb = I1._national_percentile("B", scores)
        pc = I1._national_percentile("C", scores)
        assert pa < pb < pc
