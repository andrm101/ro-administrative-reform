"""
I3 -- Sensitivity analysis: rank intervals across 8 methodological variants.

Variants = {minmax, zscore} x {equal, pca} x {geometric, arithmetic} = 8 combinations.
Reports per-county rank interval and median rank.

Follows Saisana, Saltelli & Tarantola (2005), JRSS-A.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "infra"))

EPSILON = 0.01  # floor for geometric mean — consistent with I1 and UNDP HDI approach


def _minmax(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for col in df.columns:
        lo, hi = df[col].quantile(0.05), df[col].quantile(0.95)
        if hi == lo:
            result[col] = 50.0
        else:
            result[col] = (df[col].clip(lo, hi) - lo) / (hi - lo) * 100
    return result


def _zscore(df: pd.DataFrame) -> pd.DataFrame:
    """Z-score standardise, then rescale to [0,100] via min-max."""
    z = (df - df.mean()) / df.std(ddof=1).replace(0, 1)
    return _minmax(z)


def _pca_weights(df: pd.DataFrame) -> np.ndarray:
    X = StandardScaler().fit_transform(df.values)
    pca = PCA(n_components=1, random_state=42)
    pca.fit(X)
    loadings = np.abs(pca.components_[0])
    return loadings / loadings.sum()


def _composite_geom(normed: pd.DataFrame, weights: np.ndarray) -> pd.Series:
    return normed.apply(
        lambda row: float(np.exp(np.average(np.log(np.maximum(row.values, EPSILON)), weights=weights))),
        axis=1,
    )


def _composite_arith(normed: pd.DataFrame, weights: np.ndarray) -> pd.Series:
    return normed.apply(lambda row: float(np.average(row.values, weights=weights)), axis=1)


def _build_ensemble(scores_df: pd.DataFrame) -> pd.DataFrame:
    """Return long-form DataFrame with columns: nuts3_code, variant, rank."""
    records: list[dict] = []
    n_pillars = scores_df.shape[1]
    equal_w = np.ones(n_pillars) / n_pillars
    pca_w = _pca_weights(scores_df)

    for norm_name, norm_fn in [("minmax", _minmax), ("zscore", _zscore)]:
        normed = norm_fn(scores_df)
        for weight_name, w in [("equal", equal_w), ("pca", pca_w)]:
            for agg_name, agg_fn in [("geometric", _composite_geom), ("arithmetic", _composite_arith)]:
                composite = agg_fn(normed, w)
                # Rank: 1 = highest capacity
                ranked = composite.rank(ascending=False, method="min").astype(int)
                variant = f"{norm_name}_{weight_name}_{agg_name}"
                for code, rank in ranked.items():
                    records.append({"nuts3_code": str(code), "variant": variant, "rank": int(rank)})

    return pd.DataFrame(records)


def extract(scores_df: pd.DataFrame) -> dict[str, Any]:
    """
    Args:
        scores_df: DataFrame(index=nuts3_code, columns=pillar_keys) of normalised scores.
    Returns:
        dict: nuts3_code -> {rank_interval: [min, max], rank_median: int}
    """
    ensemble = _build_ensemble(scores_df)

    result: dict[str, Any] = {}
    for code, grp in ensemble.groupby("nuts3_code"):
        ranks = grp["rank"].values
        result[str(code)] = {
            "rank_interval": [int(ranks.min()), int(ranks.max())],
            "rank_median": int(round(float(np.median(ranks)))),
        }

    n_variants = ensemble["variant"].nunique()
    print(f"  Sensitivity ensemble: {n_variants} variants")
    return result


if __name__ == "__main__":
    import I1_score_counties as I1

    print("=== I3: Sensitivity analysis ===")
    I1.extract()
    scores = pd.read_parquet(ROOT / "data" / "processed" / "infra_scores.parquet")[
        ["transport", "education", "health", "economic"]
    ]
    intervals = extract(scores)
    wide = [intervals[c]["rank_interval"][1] - intervals[c]["rank_interval"][0] for c in intervals]
    print(f"  Median rank-interval width: {int(np.median(wide))}")
    print(f"  Max rank-interval width: {max(wide)}")
