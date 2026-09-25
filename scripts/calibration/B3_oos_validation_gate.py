"""
B3 — OOS validation gate.

Estimates Barro β on 2005-2023 training data, predicts 1995-2004 hold-out.
RMSE ≤ 1.5 × in-sample residual SD → provisional: False (gate passes).

Importable: call run() to get the result dict.
Standalone: python scripts/calibration/B3_oos_validation_gate.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"

TRAIN_START = 2005
HOLDOUT_END = 2004
RMSE_MULTIPLIER = 1.5


def _gate_decision(rmse: float, threshold: float) -> bool:
    """Return True (provisional) if RMSE exceeds threshold."""
    return rmse > threshold


def run() -> dict:
    """Run OOS validation. Returns dict with provisional, rmse, threshold, conclusion."""
    panel = pd.read_parquet(PROCESSED / "ro_panel_judet.parquet")
    panel = panel.sort_values(["nuts3_code", "year"]).copy()
    panel["lag_gva"] = panel.groupby("nuts3_code")["ln_gva_per_empl"].shift(1)
    panel["dy_gva"] = panel.groupby("nuts3_code")["ln_gva_per_empl"].diff()
    panel = panel.dropna(subset=["lag_gva", "dy_gva"])

    train = panel[panel["year"] >= TRAIN_START].copy()
    holdout = panel[panel["year"] <= HOLDOUT_END].copy()

    if train.empty or holdout.empty:
        return {
            "provisional": True,
            "rmse": float("nan"),
            "threshold": float("nan"),
            "conclusion": "insufficient data for split",
        }

    # Fit Barro on training period (county + year FE via LSDV)
    res_train = smf.ols(
        "dy_gva ~ lag_gva + C(nuts3_code) + C(year)",
        data=train,
    ).fit()
    beta_train = float(res_train.params["lag_gva"])

    # County FE = mean of (dy_gva - beta * lag_gva) per county in training
    train["resid_no_lag"] = train["dy_gva"] - beta_train * train["lag_gva"]
    county_fe = train.groupby("nuts3_code")["resid_no_lag"].mean().to_dict()

    # Predict on holdout: alpha_i + beta * lag_gva.
    # The training year-FEs are NOT transferable to 1995-2004 (those years are
    # unidentified out of sample), so prediction uses only the county FE and the
    # convergence slope. The omitted year-FE variance — macro shocks of the
    # post-communist transition (1997-99 recession, pre-accession volatility) —
    # structurally inflates the OOS RMSE. That is the intended mechanism: a genuine
    # regime break between the transition era and the post-2005 sample shows up as a
    # gate failure (provisional stays True), not as model mis-specification.
    holdout = holdout[holdout["nuts3_code"].isin(county_fe)].copy()
    holdout["pred"] = (
        holdout["nuts3_code"].map(county_fe).fillna(0.0)  # fillna is a defensive no-op after the isin filter
        + beta_train * holdout["lag_gva"]
    )
    holdout = holdout.dropna(subset=["pred", "dy_gva"])

    rmse_oos = float(np.sqrt(np.mean((holdout["dy_gva"] - holdout["pred"]) ** 2)))
    resid_sd = float(np.std(res_train.resid))  # population SD (ddof=0): conservative threshold
    threshold = RMSE_MULTIPLIER * resid_sd
    provisional = _gate_decision(rmse_oos, threshold)

    conclusion = (
        f"OOS RMSE {rmse_oos:.4f} ≤ threshold {threshold:.4f} → gate PASSES (provisional=False)"
        if not provisional
        else f"OOS RMSE {rmse_oos:.4f} > threshold {threshold:.4f} → gate FAILS (provisional=True)"
    )

    return {
        "provisional": provisional,
        "rmse": rmse_oos,
        "threshold": threshold,
        "conclusion": conclusion,
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
