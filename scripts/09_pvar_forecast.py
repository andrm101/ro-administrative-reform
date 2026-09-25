"""
Stage 09 -- Mean-Group Panel VAR Forecast (Romania)

Reads:
  data/processed/ro_panel_judet.parquet
  data/processed/ro_gsynth_gaps.parquet

Writes:
  data/processed/ro_pvar_forecasts.parquet
  figures/f09_pvar_irf.png
  figures/f09_forecast_{county_name}.png  (8 showcase counties)

Method: Pesaran-Smith (1995) Mean Group VAR.
  - VAR(p, p in {1,2} by BIC) per county on maximal balanced subpanel (2000-2024)
  - Per-county constant absorbs unit FE; year effects pooled out via MG
  - IRFs from MG coefficient matrices, Cholesky-identified
  - Forecasts: residual-bootstrap CIs (500 draws)
  - Counterfactual path: gsynth ln_population at year 2024 as starting state
  - innovation_hub path: null (Stage 13 hook)

Outcomes (4): ln_population, nat_change_rate, unemployment, ln_gva_per_empl
  Note: unemployment is NUTS2-broadcast (within-region variation not captured).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.api import VAR

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "figures"
FIGURES.mkdir(exist_ok=True)

OUTCOMES = ["ln_population", "nat_change_rate", "unemployment", "ln_gva_per_empl"]
OUTCOME_LABELS = {
    "ln_population":   "Log population",
    "nat_change_rate": "Natural change rate (per 1000)",
    "unemployment":    "Unemployment rate (%)",
    "ln_gva_per_empl": "Log GVA per employed (EUR)",
}
CHOL_ORDER = ["ln_population", "nat_change_rate", "unemployment", "ln_gva_per_empl"]

YEAR_START = 2000
YEAR_END   = 2024
MIN_OBS    = 10
MAX_LAG    = 2
N_BOOT     = 500
FORECAST_YEARS = list(range(2025, 2036))
N_STEPS = len(FORECAST_YEARS)

SHOWCASE = {
    "RO211": "Bacau",
    "RO224": "Galati",
    "RO311": "Arges",
    "RO126": "Sibiu",
    "RO111": "Bihor",
    "RO421": "Arad",
    "RO215": "Suceava",
    "RO125": "Mures",
}


def load_panel() -> pd.DataFrame:
    df = pd.read_parquet(PROCESSED / "ro_panel_judet.parquet")
    return df[df["year"].between(YEAR_START, YEAR_END)].copy()


def load_gsynth_gaps() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "ro_gsynth_gaps.parquet")


def get_county_data(df: pd.DataFrame, nuts3: str) -> pd.DataFrame:
    return (
        df[df["nuts3_code"] == nuts3][["year"] + OUTCOMES]
        .dropna(subset=OUTCOMES)
        .sort_values("year")
        .reset_index(drop=True)
    )


def fit_var(data: pd.DataFrame) -> dict | None:
    if len(data) < MIN_OBS:
        return None
    mat = data[OUTCOMES].values.astype(float)
    try:
        model = VAR(mat)
        result = model.fit(maxlags=MAX_LAG, ic="bic", trend="c")
        return {
            "result": result,
            "coefs": result.coefs.copy(),
            "const": result.coefs_exog.copy(),
            "sigma_u": result.sigma_u.copy(),
            "p": result.k_ar,
        }
    except Exception:
        return None


def mean_group_pool(
    county_fits: dict[str, dict | None],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    valid = {k: v for k, v in county_fits.items() if v is not None}
    K = len(OUTCOMES)
    coef_list  = [v["coefs"]   for v in valid.values()]
    const_list = [v["const"]   for v in valid.values()]
    sigma_list = [v["sigma_u"] for v in valid.values()]
    max_p = max(c.shape[0] for c in coef_list)

    def pad(A: np.ndarray) -> np.ndarray:
        if A.shape[0] < max_p:
            return np.concatenate([A, np.zeros((max_p - A.shape[0], K, K))], axis=0)
        return A

    A_arr     = np.stack([pad(c) for c in coef_list])
    const_arr = np.stack([c.squeeze() for c in const_list])
    sigma_arr = np.stack(sigma_list)
    N = len(A_arr)
    A_mg     = A_arr.mean(axis=0)
    A_se     = A_arr.std(axis=0) / np.sqrt(N)
    const_mg = const_arr.mean(axis=0)
    sigma_mg = sigma_arr.mean(axis=0)
    print(f"  Mean Group pool: {N} counties, max_p={max_p}, K={K}")
    return A_mg, A_se, const_mg, sigma_mg


def compute_irfs(A_mg: np.ndarray, Sigma_mg: np.ndarray, n_periods: int = 20) -> np.ndarray:
    K = Sigma_mg.shape[0]
    p = A_mg.shape[0]
    idx = [OUTCOMES.index(v) for v in CHOL_ORDER]
    A_r = A_mg[:, :, :][:, idx, :][:, :, idx]
    S_r = Sigma_mg[np.ix_(idx, idx)]
    try:
        P = np.linalg.cholesky(S_r)
    except np.linalg.LinAlgError:
        P = np.diag(np.sqrt(np.diag(S_r)))
    Phi = np.zeros((n_periods + 1, K, K))
    Phi[0] = np.eye(K)
    for h in range(1, n_periods + 1):
        for j in range(1, min(p, h) + 1):
            Phi[h] += A_r[j - 1] @ Phi[h - j]
    return np.einsum("hij,jk->hik", Phi, P)


def plot_irfs(irfs: np.ndarray, out_path: Path) -> None:
    K = len(CHOL_ORDER)
    short = ["ln Pop", "Nat. Chg", "Unemp", "ln GVA/emp"]
    fig, axes = plt.subplots(K, K, figsize=(12, 10), sharex=True)
    fig.suptitle(
        "Mean-Group Panel VAR -- Impulse Response Functions\n(Cholesky, 20-year horizon)",
        fontsize=11,
    )
    for r in range(K):
        for c in range(K):
            ax = axes[r, c]
            ax.plot(range(1, 21), irfs[1:, r, c], color="#4d7cff", lw=1.5)
            ax.axhline(0, color="grey", lw=0.7, ls="--")
            ax.set_title(f"Shock: {short[c]}", fontsize=7, pad=2)
            if c == 0:
                ax.set_ylabel(short[r], fontsize=7)
            ax.tick_params(labelsize=6)
    for ax in axes[-1]:
        ax.set_xlabel("Years", fontsize=7)
    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path.name}")


def _project_forward(
    start_state: list[np.ndarray],
    coefs: np.ndarray,
    const: np.ndarray,
    residuals: np.ndarray,
    n_steps: int,
    n_boot: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    K = coefs.shape[1]
    p = coefs.shape[0]

    def _one(state: list[np.ndarray], resid: np.ndarray | None) -> np.ndarray:
        st = [s.copy() for s in state]
        path = np.zeros((n_steps, K))
        for h in range(n_steps):
            y = const.copy()
            for lag in range(p):
                y += coefs[lag] @ st[lag]
            if resid is not None:
                y += resid[h % len(resid)]
            path[h] = y
            st.insert(0, y)
            if len(st) > p:
                st.pop()
        return path

    point = _one(start_state, None)
    boot = np.zeros((n_boot, n_steps, K))
    T_res = len(residuals)
    for b in range(n_boot):
        idx = np.random.randint(0, T_res, size=n_steps)
        boot[b] = _one(start_state, residuals[idx])
    lo80 = np.percentile(boot, 10, axis=0)
    hi80 = np.percentile(boot, 90, axis=0)
    lo95 = np.percentile(boot, 2.5, axis=0)
    hi95 = np.percentile(boot, 97.5, axis=0)
    return point, lo80, hi80, lo95, hi95


def forecast_county(
    county_fit: dict | None,
    mg_coefs: np.ndarray,
    mg_const: np.ndarray,
    mg_sigma: np.ndarray,
    state_start: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if county_fit is not None:
        coefs  = county_fit["coefs"]
        const  = county_fit["const"].squeeze()
        resids = county_fit["result"].resid
        p      = county_fit["p"]
        data   = county_fit["result"].model.endog
        history = [data[-(lag + 1)] for lag in range(p)]
        history[0] = state_start
    else:
        coefs  = mg_coefs
        const  = mg_const
        resids = np.random.multivariate_normal(
            np.zeros(mg_sigma.shape[0]), mg_sigma, size=50
        )
        p = coefs.shape[0]
        history = [state_start] + [state_start] * (p - 1)
    return _project_forward(history[:p], coefs, const, resids, N_STEPS, N_BOOT)


def plot_fan_chart(
    county_name: str,
    nuts3: str,
    sq_fc: dict,
    cf_fc: dict | None,
    out_path: Path,
) -> None:
    show_vars = ["ln_population", "unemployment"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    fig.suptitle(f"{county_name} ({nuts3}) -- VAR Forecast 2025-2035", fontsize=11)
    for col, var in enumerate(show_vars):
        ax = axes[col]
        vi = OUTCOMES.index(var)
        yrs = FORECAST_YEARS
        sq = sq_fc
        ax.fill_between(yrs, sq["lo95"][:, vi], sq["hi95"][:, vi], alpha=0.12, color="#4d7cff")
        ax.fill_between(yrs, sq["lo80"][:, vi], sq["hi80"][:, vi], alpha=0.22, color="#4d7cff")
        ax.plot(yrs, sq["point"][:, vi], color="#4d7cff", lw=2, label="Status quo")
        if cf_fc is not None:
            cf = cf_fc
            ax.fill_between(yrs, cf["lo95"][:, vi], cf["hi95"][:, vi], alpha=0.10, color="#4dffb4")
            ax.fill_between(yrs, cf["lo80"][:, vi], cf["hi80"][:, vi], alpha=0.18, color="#4dffb4")
            ax.plot(yrs, cf["point"][:, vi], color="#16a34a", lw=2, ls="--", label="Counterfactual")
        ax.set_title(OUTCOME_LABELS[var], fontsize=9)
        ax.set_xlabel("Year")
        ax.axvline(2025, color="grey", lw=0.7, ls=":")
        if col == 0:
            ax.legend(fontsize=7)
    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    np.random.seed(42)
    print("=== Stage 09: Mean-Group Panel VAR (Romania) ===\n")

    panel = load_panel()
    gaps  = load_gsynth_gaps()

    gaps_2024 = (
        gaps[gaps["year"] == YEAR_END][["nuts3_code", "counterfactual"]]
        .set_index("nuts3_code")["counterfactual"]
        .to_dict()
    )

    all_nuts3 = panel["nuts3_code"].unique()

    print("Fitting per-county VAR models...")
    county_fits: dict[str, dict | None] = {}
    failed = 0
    for nuts3 in all_nuts3:
        data = get_county_data(panel, nuts3)
        if len(data) < MIN_OBS:
            county_fits[nuts3] = None
            failed += 1
            continue
        fit = fit_var(data)
        county_fits[nuts3] = fit
        if fit is None:
            failed += 1

    n_valid = sum(1 for v in county_fits.values() if v is not None)
    print(f"  Valid fits: {n_valid}/{len(all_nuts3)}  (failed/insufficient: {failed})\n")

    print("Pooling via Mean Group estimator...")
    A_mg, A_se, const_mg, Sigma_mg = mean_group_pool(county_fits)

    print("Computing Mean-Group IRFs...")
    irfs = compute_irfs(A_mg, Sigma_mg, n_periods=20)
    plot_irfs(irfs, FIGURES / "f09_pvar_irf.png")

    print(f"\nForecasting {N_STEPS} steps for showcase counties, {N_BOOT} bootstrap draws...")
    rows = []

    for nuts3, county_name in SHOWCASE.items():
        print(f"  {county_name} ({nuts3})")
        fit = county_fits.get(nuts3)

        county_data = get_county_data(panel, nuts3)
        obs_end = county_data[county_data["year"] == YEAR_END]
        if obs_end.empty:
            obs_end = county_data.tail(1)
        if obs_end.empty:
            print(f"    [WARN] No data for {county_name}, skipping")
            continue

        state_end = obs_end[OUTCOMES].values[0].astype(float)

        pt, l80, h80, l95, h95 = forecast_county(fit, A_mg, const_mg, Sigma_mg, state_end)
        sq = {"point": pt, "lo80": l80, "hi80": h80, "lo95": l95, "hi95": h95}

        for h, yr in enumerate(FORECAST_YEARS):
            for vi, var in enumerate(OUTCOMES):
                rows.append({
                    "nuts3_code": nuts3, "county_name": county_name,
                    "year": yr, "variable": var, "path": "status_quo",
                    "value": pt[h, vi],
                    "lo80": l80[h, vi], "hi80": h80[h, vi],
                    "lo95": l95[h, vi], "hi95": h95[h, vi],
                })

        cf_ln_pop = gaps_2024.get(nuts3)
        cf_store = None
        if cf_ln_pop is not None and not np.isnan(float(cf_ln_pop)):
            state_cf = state_end.copy()
            pop_idx = OUTCOMES.index("ln_population")
            state_cf[pop_idx] = float(cf_ln_pop)
            pt_cf, l80_cf, h80_cf, l95_cf, h95_cf = forecast_county(
                fit, A_mg, const_mg, Sigma_mg, state_cf
            )
            cf_store = {"point": pt_cf, "lo80": l80_cf, "hi80": h80_cf,
                        "lo95": l95_cf, "hi95": h95_cf}
            for h, yr in enumerate(FORECAST_YEARS):
                for vi, var in enumerate(OUTCOMES):
                    rows.append({
                        "nuts3_code": nuts3, "county_name": county_name,
                        "year": yr, "variable": var, "path": "counterfactual",
                        "value": pt_cf[h, vi],
                        "lo80": l80_cf[h, vi], "hi80": h80_cf[h, vi],
                        "lo95": l95_cf[h, vi], "hi95": h95_cf[h, vi],
                    })

        for yr in FORECAST_YEARS:
            for var in OUTCOMES:
                rows.append({
                    "nuts3_code": nuts3, "county_name": county_name,
                    "year": yr, "variable": var, "path": "innovation_hub",
                    "value": None, "lo80": None, "hi80": None, "lo95": None, "hi95": None,
                })

        out_fig = FIGURES / f"f09_forecast_{county_name.lower()}.png"
        plot_fan_chart(county_name, nuts3, sq, cf_store, out_fig)
        print(f"    Saved: {out_fig.name}")

    forecasts = pd.DataFrame(rows)
    out_path = PROCESSED / "ro_pvar_forecasts.parquet"
    forecasts.to_parquet(out_path, index=False)
    print(f"\nSaved: data/processed/ro_pvar_forecasts.parquet  ({len(forecasts)} rows)")
    print(f"  Counties: {forecasts['nuts3_code'].nunique()}")
    print(f"  Paths: {forecasts['path'].unique().tolist()}")
    print(f"  Years: {forecasts['year'].min()}-{forecasts['year'].max()}")
    print("\n=== Stage 09 complete ===")


if __name__ == "__main__":
    main()
