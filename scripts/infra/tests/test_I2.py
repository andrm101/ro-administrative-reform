"""Tests for I2_flag_divergence.py"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import geopandas as gpd
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import I2_flag_divergence as I2


class TestStudentizedLooResiduals:
    def test_outlier_gets_high_absolute_t(self):
        """A point far from the regression line has |t| > 2."""
        rng = np.random.default_rng(42)
        x = np.linspace(0, 100, 20)
        y = 0.5 * x + rng.normal(0, 2, 20)
        # Inject one outlier
        y[10] = y[10] + 40
        resids = I2._studentized_loo_residuals(x, y)
        assert abs(resids[10]) > 2.0

    def test_inlier_has_low_t(self):
        rng = np.random.default_rng(0)
        x = np.linspace(0, 100, 30)
        y = 0.3 * x + rng.normal(0, 1, 30)
        resids = I2._studentized_loo_residuals(x, y)
        # Most should be within ±2
        assert (np.abs(resids) < 2).mean() > 0.8

    def test_length_matches_input(self):
        x = np.arange(10, dtype=float)
        y = np.arange(10, dtype=float) + np.random.normal(0, 0.1, 10)
        resids = I2._studentized_loo_residuals(x, y)
        assert len(resids) == 10


class TestLisaQuadrant:
    def _make_grid_gdf(self) -> gpd.GeoDataFrame:
        """4-county 2x2 grid for testing LISA."""
        polys = [
            Polygon([(0,0),(1,0),(1,1),(0,1)]),
            Polygon([(1,0),(2,0),(2,1),(1,1)]),
            Polygon([(0,1),(1,1),(1,2),(0,2)]),
            Polygon([(1,1),(2,1),(2,2),(1,2)]),
        ]
        return gpd.GeoDataFrame(
            {"nuts3_code": ["A","B","C","D"]},
            geometry=polys,
            crs="EPSG:4326"
        )

    def test_returns_valid_quadrants(self):
        gdf = self._make_grid_gdf()
        capacity = pd.Series({"A": 90.0, "B": 20.0, "C": 80.0, "D": 30.0})
        quads = I2._lisa_quadrants(capacity, gdf)
        assert set(quads.values).issubset({"HH", "HL", "LH", "LL", "NS"})

    def test_index_matches_nuts3_codes(self):
        gdf = self._make_grid_gdf()
        capacity = pd.Series({"A": 50.0, "B": 50.0, "C": 50.0, "D": 50.0})
        quads = I2._lisa_quadrants(capacity, gdf)
        assert set(quads.index) == {"A", "B", "C", "D"}


class TestClassifyDivergence:
    def test_high_cap_low_outcome_is_bottleneck(self):
        result = I2._classify_divergence(2.5, "HL")
        assert result == "structural_bottleneck"

    def test_low_cap_high_outcome_is_fragility(self):
        result = I2._classify_divergence(-2.5, "LH")
        assert result == "latent_fragility"

    def test_within_threshold_is_none(self):
        assert I2._classify_divergence(1.0, "HL") is None
        assert I2._classify_divergence(-1.0, "LH") is None
