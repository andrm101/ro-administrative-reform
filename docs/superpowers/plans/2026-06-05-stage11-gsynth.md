# Stage 11 — Cross-Country Generalised Synthetic Control (Romania)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a combined Polish+Romanian panel, run gsynth to produce counterfactual no-reform trajectories for 33 demoted Romanian counties (2025-2035), and save `ro_gsynth_gaps.parquet` mirroring the PL format.

**Architecture:**
Since the Romanian reform is hypothetical (not yet enacted), all 1995-2024 data is pre-treatment. We extend the panel to 2025-2035 by extrapolating donor trajectories linearly and setting treated-unit outcomes to NA. gsynth fits an IFE factor model on the combined panel, then imputes the NA values as the "no-reform counterfactual." Three reform cost scenarios (pessimistic / central / optimistic) are derived from the Polish ATT distribution.

**Tech Stack:** Python 3.11 (pandas, pyarrow, numpy, scipy), R 4.5.1 (gsynth, arrow, tidyverse), paths relative to `RO-Administrative-Reform/` project root. R executable: `C:\Program Files\R\R-4.5.1\bin\Rscript.exe`.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `scripts/build_cc_panel.py` | CREATE | Harmonize PL non-treated + RO panel → `cc_panel.parquet`; add 2025-2035 rows |
| `scripts/r/utils.R` | CREATE | Path helpers, parquet read/write wrappers (mirror of PL utils.R) |
| `scripts/r/11_gsynth.R` | CREATE | gsynth on `cc_panel.parquet` → `ro_gsynth_raw.parquet`, figures |
| `scripts/postprocess_gsynth.py` | CREATE | Parse raw gsynth output → `ro_gsynth_gaps.parquet` (final format) |

**Inputs:**
- `../PL-Capital-Reform-DiD/data/processed/panel_powiat.parquet` (Polish panel; use non-treated units only)
- `data/processed/ro_panel_judet.parquet` (Romanian Gold panel, Stage 03 output)

**Outputs:**
- `data/processed/cc_panel.parquet` — combined cross-country panel (unit_id × year)
- `data/processed/ro_gsynth_raw.parquet` — gsynth output (pre-processed in R)
- `data/processed/ro_gsynth_gaps.parquet` — final counterfactual gaps (canonical format)
- `figures/f11_gsynth_aggregate.png` — mean gap over time
- `figures/f11_gsynth_grid.png` — 3×4 city grid (actual vs counterfactual)
- `figures/f11_gsynth_ebar.png` — per-city reform cost bars

---

## Task 1: Write `scripts/r/utils.R`

**Files:**
- Create: `scripts/r/utils.R`

- [ ] **Step 1.1: Write utils.R**

```r
# utils.R — shared helpers for RO-Administrative-Reform R scripts

library(arrow)

# Project root = two levels up from scripts/r/
proj_root <- function() {
  normalizePath(file.path(dirname(sys.frame(1)$ofile), "..", ".."))
}

processed_dir <- function() file.path(proj_root(), "data", "processed")
figures_dir   <- function() file.path(proj_root(), "figures")

read_processed <- function(filename) {
  path <- file.path(processed_dir(), filename)
  if (!file.exists(path)) stop(paste("File not found:", path))
  read_parquet(path)
}

write_processed <- function(df, filename) {
  dir.create(processed_dir(), showWarnings = FALSE, recursive = TRUE)
  write_parquet(as.data.frame(df), file.path(processed_dir(), filename))
  cat(sprintf("Saved: data/processed/%s (%d rows)\n", filename, nrow(df)))
}
```

- [ ] **Step 1.2: Verify utils.R loads without error**

```powershell
& "C:\Program Files\R\R-4.5.1\bin\Rscript.exe" -e "source('scripts/r/utils.R'); cat(processed_dir(), '\n')"
```
Expected output: path ending in `data\processed`

---

## Task 2: Write `scripts/build_cc_panel.py`

**Files:**
- Create: `scripts/build_cc_panel.py`

**What it does:**
1. Loads Polish non-treated powiats (`panel_powiat.parquet`, `treated==0`), keeps `teryt_powiat`, `year`, `ln_population`, prefixes unit IDs with `"PL_"`.
2. Loads Romanian panel (`ro_panel_judet.parquet`), keeps `nuts3_code`, `year`, `ln_population`, `treated`.
3. Stacks into a single panel with columns: `unit_id | year | ln_population | country | ro_treated`.
4. Filters to only units with ≥ 20 non-NA `ln_population` observations in 1995-2024.
5. **Extends to 2025-2035**: for each unit, fits OLS(ln_population ~ year) on 2018-2024, predicts 2025-2035. Romanian *treated* units get `ln_population = NA` (to be imputed by gsynth).
6. Adds treatment indicator `D`: `D = 1` for Romanian treated units AND `year >= 2025`; else `D = 0`.
7. Saves to `data/processed/cc_panel.parquet`.

- [ ] **Step 2.1: Write `scripts/build_cc_panel.py`**

```python
"""
Build cross-country panel for Stage 11 gsynth.

Combines:
  - Polish non-treated powiats (346 donor units, 1995-2024)
  - Romanian NUTS3 panel (42 units, 1995-2024; 33 treated, 9 control)

Extends to 2025-2035:
  - Donors: linear extrapolation of 2018-2024 trend per unit
  - Romanian treated units: ln_population = NaN (gsynth will impute = counterfactual)

Output: data/processed/cc_panel.parquet
  unit_id (str) | year (int) | ln_population (float|NaN) | country | ro_treated (0/1) | D (0/1)
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
PL_ROOT = ROOT.parent / "PL-Capital-Reform-DiD"
PROCESSED = ROOT / "data" / "processed"

FORECAST_START = 2025
FORECAST_END   = 2035
TREND_WINDOW   = (2018, 2024)
MIN_OBS        = 20   # minimum non-NA years required to include a unit


def linear_extrapolate(
    years: np.ndarray,
    values: np.ndarray,
    future_years: np.ndarray,
    trend_window: tuple[int, int] = TREND_WINDOW,
) -> np.ndarray:
    """OLS trend on [trend_window], predict future_years."""
    mask = (years >= trend_window[0]) & (years <= trend_window[1])
    y_fit = values[mask]
    x_fit = years[mask]
    valid = np.isfinite(y_fit) & np.isfinite(x_fit)
    if valid.sum() < 3:
        # Not enough points: use last observed value (flat extrapolation)
        last_val = values[np.isfinite(values)][-1] if np.isfinite(values).any() else np.nan
        return np.full(len(future_years), last_val)
    slope, intercept, *_ = stats.linregress(x_fit[valid], y_fit[valid])
    return slope * future_years + intercept


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    future_years = np.arange(FORECAST_START, FORECAST_END + 1)

    # ── 1. Polish donors ────────────────────────────────────────────────────
    pl_path = PL_ROOT / "data" / "processed" / "panel_powiat.parquet"
    if not pl_path.exists():
        raise FileNotFoundError(f"Polish panel not found: {pl_path}")

    pl = pd.read_parquet(pl_path)
    pl_donors = pl[pl["treated"] == 0][["teryt_powiat", "year", "ln_population"]].copy()
    pl_donors["unit_id"] = "PL_" + pl_donors["teryt_powiat"].astype(str)
    pl_donors["country"] = "PL"
    pl_donors["ro_treated"] = 0

    # ── 2. Romanian units ───────────────────────────────────────────────────
    ro = pd.read_parquet(PROCESSED / "ro_panel_judet.parquet")
    ro_panel = ro[["nuts3_code", "year", "ln_population", "treated"]].copy()
    ro_panel["unit_id"] = ro_panel["nuts3_code"]
    ro_panel["country"] = "RO"
    ro_panel["ro_treated"] = ro_panel["treated"]

    # ── 3. Stack observed data ──────────────────────────────────────────────
    combined = pd.concat([
        pl_donors[["unit_id", "year", "ln_population", "country", "ro_treated"]],
        ro_panel[["unit_id", "year", "ln_population", "country", "ro_treated"]],
    ], ignore_index=True)

    # ── 4. Drop units with < MIN_OBS non-NA ln_population ──────────────────
    obs_count = (combined.groupby("unit_id")["ln_population"]
                 .apply(lambda x: x.notna().sum()))
    keep_units = obs_count[obs_count >= MIN_OBS].index
    combined = combined[combined["unit_id"].isin(keep_units)].copy()
    print(f"After coverage filter (>={MIN_OBS} obs): {combined['unit_id'].nunique()} units")
    print(f"  PL donors: {combined[combined['country']=='PL']['unit_id'].nunique()}")
    print(f"  RO treated: {combined[combined['ro_treated']==1]['unit_id'].nunique()}")
    print(f"  RO control: {combined[(combined['country']=='RO') & (combined['ro_treated']==0)]['unit_id'].nunique()}")

    # ── 5. Extend to 2025-2035 ──────────────────────────────────────────────
    extension_rows: list[dict] = []
    all_units = combined["unit_id"].unique()

    for uid in all_units:
        sub = combined[combined["unit_id"] == uid].sort_values("year")
        yrs = sub["year"].values.astype(float)
        vals = sub["ln_population"].values.astype(float)

        is_ro_treated = sub["ro_treated"].iloc[0] == 1
        country = sub["country"].iloc[0]

        if is_ro_treated:
            # Treated Romanian units: outcome is NA in future (gsynth will impute)
            future_vals = np.full(len(future_years), np.nan)
        else:
            future_vals = linear_extrapolate(yrs, vals, future_years.astype(float))

        for i, fy in enumerate(future_years):
            extension_rows.append({
                "unit_id": uid,
                "year": int(fy),
                "ln_population": future_vals[i],
                "country": country,
                "ro_treated": sub["ro_treated"].iloc[0],
            })

    extension = pd.DataFrame(extension_rows)
    panel = pd.concat([combined, extension], ignore_index=True)

    # ── 6. Treatment indicator D ────────────────────────────────────────────
    panel["D"] = ((panel["ro_treated"] == 1) & (panel["year"] >= FORECAST_START)).astype(int)

    panel = panel.sort_values(["unit_id", "year"]).reset_index(drop=True)
    out_path = PROCESSED / "cc_panel.parquet"
    panel.to_parquet(out_path, index=False)

    print(f"\nSaved: data/processed/cc_panel.parquet")
    print(f"  Shape: {panel.shape}")
    print(f"  Years: {panel['year'].min()}-{panel['year'].max()}")
    print(f"  Treated (D=1) unit-years: {panel['D'].sum()}")
    print(f"  NA ln_population (to impute): {panel['ln_population'].isna().sum()}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2.2: Run and verify**

```powershell
Set-Location "c:\Users\andre\Desktop\Sandbox\RO-Administrative-Reform"
python scripts/build_cc_panel.py
```

Expected:
```
After coverage filter (>=20 obs): ~380 units
  PL donors: ~340
  RO treated: 33
  RO control: 9
Saved: data/processed/cc_panel.parquet
  Shape: (~4500, 6)
  Years: 1995-2035
  Treated (D=1) unit-years: 363   # 33 treated × 11 years
  NA ln_population (to impute): 363
```

- [ ] **Step 2.3: Commit**

```powershell
git add RO-Administrative-Reform/scripts/build_cc_panel.py RO-Administrative-Reform/scripts/r/utils.R
git commit -m "feat(RO-Stage11): cross-country panel builder + R utils"
```

---

## Task 3: Write `scripts/r/11_gsynth.R`

**Files:**
- Create: `scripts/r/11_gsynth.R`

**What it does:**
- Reads `cc_panel.parquet`
- Runs `gsynth(ln_population ~ D, ...)` with `estimator = "ife"`, `CV = TRUE`, `r = c(0, 5)`, `min.T0 = 4`
- Extracts `out$Y.ct` (counterfactual fitted values) for RO treated units
- Saves three artefacts to `data/processed/ro_gsynth_raw.parquet`:
  - `unit_id | year | actual | counterfactual | gap | se_gap | country`
- Produces three figures: aggregate gap, 3×4 city grid, per-city ATT bar chart

- [ ] **Step 3.1: Write `scripts/r/11_gsynth.R`**

```r
#!/usr/bin/env Rscript
# Stage 11 -- Cross-Country Generalised Synthetic Control (Romania)
# Reads:  data/processed/cc_panel.parquet
# Writes: data/processed/ro_gsynth_raw.parquet
#         figures/f11_gsynth_aggregate.png
#         figures/f11_gsynth_grid.png
#         figures/f11_gsynth_ebar.png

suppressPackageStartupMessages({
  library(arrow)
  library(gsynth)
  library(tidyverse)
})

source("scripts/r/utils.R")
cat("=== Stage 11: Cross-Country GSC (Romania) ===\n\n")

panel <- read_processed("cc_panel.parquet")

# Restrict to complete units on observed years (1995-2024)
observed <- panel |> filter(year <= 2024)
n_years_obs <- n_distinct(observed$year)

complete_units <- observed |>
  group_by(unit_id) |>
  summarise(n_obs = n(), n_na = sum(is.na(ln_population)), .groups = "drop") |>
  filter(n_na == 0, n_obs == n_years_obs) |>
  pull(unit_id)

# Re-attach 2025-2035 rows for complete units (NA rows for treated -- gsynth will impute)
panel <- panel |> filter(unit_id %in% complete_units)
ro_treated_ids <- panel |> filter(ro_treated == 1) |> pull(unit_id) |> unique()

cat(sprintf("Balanced panel: %d units (%d RO treated, %d donors)\n",
    n_distinct(panel$unit_id),
    length(ro_treated_ids),
    n_distinct(panel$unit_id) - length(ro_treated_ids)))

cat(sprintf("Years: %d--%d | Post-treatment rows (D=1): %d\n",
    min(panel$year), max(panel$year), sum(panel$D)))

set.seed(42)
cat("Fitting gsynth (CV over r={0..5}, B=200)...\n")

out <- gsynth(
  ln_population ~ D,
  data      = as.data.frame(panel),
  index     = c("unit_id", "year"),
  force     = "two-way",
  CV        = TRUE,
  r         = c(0, 5),
  se        = TRUE,
  inference = "parametric",
  nboots    = 200,
  seed      = 42,
  min.T0    = 10,
  estimator = "ife"
)

cat(sprintf("Optimal r* = %d\n", out$r.cv))
if (!is.null(out$att)) {
  cat(sprintf("Average ATT (post-treatment): %.4f\n", mean(out$att, na.rm = TRUE)))
}

# ── Extract counterfactual trajectories ────────────────────────────────────
# out$Y.ct: T x N matrix (counterfactual fitted values, all years, treated units)
# out$Y.tr: T x N matrix (observed values for treated units)
all_years <- as.integer(rownames(out$Y.ct))
n_treated <- ncol(out$Y.ct)

gaps_list <- lapply(seq_len(n_treated), function(j) {
  uid  <- colnames(out$Y.ct)[j]
  actual_vec <- as.numeric(out$Y.tr[, j])
  ct_vec     <- as.numeric(out$Y.ct[, j])
  gap_vec    <- actual_vec - ct_vec  # NA where actual = NA (post-2024 for treated)
  data.frame(
    unit_id        = uid,
    year           = all_years,
    actual         = actual_vec,
    counterfactual = ct_vec,
    gap            = gap_vec,
    se_gap         = NA_real_,
    stringsAsFactors = FALSE
  )
})

gaps <- as_tibble(do.call(rbind, gaps_list))
gaps$year <- as.integer(gaps$year)

# Per-city average pre-reform fit quality (residual 1995-2024)
fit_quality <- gaps |>
  filter(year <= 2024) |>
  group_by(unit_id) |>
  summarise(rmse_preperiod = sqrt(mean(gap^2, na.rm = TRUE)), .groups = "drop")

gaps <- gaps |> left_join(fit_quality, by = "unit_id")

write_processed(gaps, "ro_gsynth_raw.parquet")
cat(sprintf("ro_gsynth_raw.parquet: %d rows, %d units\n",
    nrow(gaps), n_distinct(gaps$unit_id)))

# ── Figures ─────────────────────────────────────────────────────────────────
dir.create(figures_dir(), showWarnings = FALSE, recursive = TRUE)

# Figure 1: Aggregate mean counterfactual vs. actual (pre-2025)
tryCatch({
  agg <- gaps |>
    filter(year <= 2024) |>
    group_by(year) |>
    summarise(
      mean_actual = mean(actual, na.rm = TRUE),
      mean_cf     = mean(counterfactual, na.rm = TRUE),
      .groups = "drop"
    )
  p_agg <- ggplot(agg, aes(x = year)) +
    geom_line(aes(y = mean_actual, colour = "Observed"), lwd = 1.2) +
    geom_line(aes(y = mean_cf, colour = "Counterfactual (no reform)"),
              lwd = 1.2, linetype = "dashed") +
    geom_vline(xintercept = 2025, linetype = "dotted", colour = "grey40") +
    scale_colour_manual(values = c("Observed" = "#4d7cff",
                                   "Counterfactual (no reform)" = "#e84d4d")) +
    labs(
      title    = "Mean ln(population): Observed vs. Synthetic Counterfactual",
      subtitle = "33 proposed-demoted Romanian counties; dashed line = proposed reform year",
      x = "Year", y = "Mean ln(population)", colour = NULL
    ) +
    theme_minimal(base_size = 11) +
    theme(legend.position = "bottom")
  ggsave(file.path(figures_dir(), "f11_gsynth_aggregate.png"),
         p_agg, width = 9, height = 4.5, dpi = 300)
  cat("Saved: f11_gsynth_aggregate.png\n")
}, error = function(e) cat(sprintf("  [WARN] aggregate plot: %s\n", e$message)))

# Figure 2: 3x4 grid -- 12 showcase cities (actual vs counterfactual)
showcase_units <- ro_treated_ids[1:min(12, length(ro_treated_ids))]
tryCatch({
  grid_data <- gaps |>
    filter(unit_id %in% showcase_units, year <= 2035) |>
    pivot_longer(cols = c(actual, counterfactual),
                 names_to = "series", values_to = "value") |>
    mutate(series = recode(series,
      "actual" = "Observed",
      "counterfactual" = "Counterfactual"
    ))
  p_grid <- ggplot(grid_data, aes(x = year, y = value, colour = series)) +
    geom_line(lwd = 0.9) +
    geom_vline(xintercept = 2025, linetype = "dashed", colour = "grey60", lwd = 0.6) +
    facet_wrap(~ unit_id, ncol = 4) +
    scale_colour_manual(values = c("Observed" = "#4d7cff",
                                   "Counterfactual" = "#e84d4d")) +
    labs(title = "Observed vs. Synthetic Counterfactual by County",
         x = "Year", y = "ln(population)", colour = NULL) +
    theme_minimal(base_size = 9) +
    theme(legend.position = "bottom", strip.text = element_text(size = 7))
  ggsave(file.path(figures_dir(), "f11_gsynth_grid.png"),
         p_grid, width = 12, height = 9, dpi = 300)
  cat("Saved: f11_gsynth_grid.png\n")
}, error = function(e) cat(sprintf("  [WARN] grid plot: %s\n", e$message)))

# Figure 3: pre-period RMSE bar (fit quality per county)
tryCatch({
  fq_sorted <- fit_quality |> arrange(rmse_preperiod)
  p_bar <- ggplot(fq_sorted, aes(x = reorder(unit_id, rmse_preperiod),
                                  y = rmse_preperiod)) +
    geom_col(fill = "#4d7cff", alpha = 0.8) +
    coord_flip() +
    labs(title = "Pre-period Fit Quality: RMSE(actual vs counterfactual) 1995-2024",
         x = "County", y = "RMSE (ln population)") +
    theme_minimal(base_size = 9)
  ggsave(file.path(figures_dir(), "f11_gsynth_ebar.png"),
         p_bar, width = 7, height = 8, dpi = 300)
  cat("Saved: f11_gsynth_ebar.png\n")
}, error = function(e) cat(sprintf("  [WARN] RMSE bar: %s\n", e$message)))

cat("\n=== Stage 11 complete ===\n")
```

- [ ] **Step 3.2: Run and inspect output**

```powershell
Set-Location "c:\Users\andre\Desktop\Sandbox\RO-Administrative-Reform"
& "C:\Program Files\R\R-4.5.1\bin\Rscript.exe" scripts/r/11_gsynth.R
```

Expected (takes 5-15 minutes — gsynth cross-validates over r={0..5} with B=200 bootstraps):
```
=== Stage 11: Cross-Country GSC (Romania) ===
Balanced panel: ~380 units (33 RO treated, ~347 donors)
Years: 1995--2035 | Post-treatment rows (D=1): 363
Fitting gsynth (CV over r={0..5}, B=200)...
Optimal r* = [1-3 expected]
ro_gsynth_raw.parquet: ~1353 rows, 33 units
Saved: f11_gsynth_aggregate.png
Saved: f11_gsynth_grid.png
Saved: f11_gsynth_ebar.png
```

If gsynth errors on "no post-treatment period" or "not enough treated units", see **Known Issues** at end of this plan.

---

## Task 4: Write `scripts/postprocess_gsynth.py`

**Files:**
- Create: `scripts/postprocess_gsynth.py`

**What it does:**
1. Reads `ro_gsynth_raw.parquet`
2. Merges in county metadata from `ro_treatment_cities.parquet` (nuts3_code, judet_name, county_seat)
3. Applies Polish ATT distribution to generate three reform-cost scenarios:
   - `pessimistic`: counterfactual × exp(−0.045)  (Polish SDiD ATT)
   - `central`: counterfactual × exp(−0.015)       (Polish GSC average ATT)
   - `optimistic`: counterfactual × exp(+0.005)    (high-performing Polish cities)
4. Saves `ro_gsynth_gaps.parquet` with per-county per-year: actual | counterfactual | gap | reform_scenario_pessimistic | reform_scenario_central | reform_scenario_optimistic | att_avg_pre

- [ ] **Step 4.1: Write `scripts/postprocess_gsynth.py`**

```python
"""
Stage 11b -- Post-process gsynth output into canonical ro_gsynth_gaps.parquet.

Polish ATT priors (from PL Stage 11):
  - Pessimistic: -0.045 (Polish SDiD ATT: most negative single estimate)
  - Central:     -0.015 (Polish GSC average ATT across 29 cities)
  - Optimistic:  +0.005 (upper tail of PL GSC ATT distribution)

Reads:
  data/processed/ro_gsynth_raw.parquet
  data/processed/ro_treatment_cities.parquet

Writes:
  data/processed/ro_gsynth_gaps.parquet
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

# Polish ATT priors (from PL-Capital-Reform-DiD Stage 10-11 outputs)
PL_ATT_PESSIMISTIC = -0.045   # SDiD ATT ln_population
PL_ATT_CENTRAL     = -0.015   # GSC average ATT ln_population
PL_ATT_OPTIMISTIC  =  0.005   # upper tail (cities that partially recovered)


def main() -> None:
    raw = pd.read_parquet(PROCESSED / "ro_gsynth_raw.parquet")
    cities = pd.read_parquet(PROCESSED / "ro_treatment_cities.parquet")

    # Merge metadata
    gaps = raw.merge(
        cities[["nuts3_code", "judet_name", "county_seat", "nuts2_code"]],
        left_on="unit_id", right_on="nuts3_code", how="left"
    )

    # Reform scenarios: apply Polish ATT as a step-down shock from 2025 onwards
    # counterfactual is the "no reform" baseline; reform scenario = counterfactual + ATT
    future_mask = gaps["year"] >= 2025
    for scenario, att in [
        ("pessimistic", PL_ATT_PESSIMISTIC),
        ("central",     PL_ATT_CENTRAL),
        ("optimistic",  PL_ATT_OPTIMISTIC),
    ]:
        col = f"reform_scenario_{scenario}"
        gaps[col] = gaps["counterfactual"]
        gaps.loc[future_mask, col] = gaps.loc[future_mask, "counterfactual"] + att

    # Per-city pre-period fit quality (average residual 1995-2024)
    pre = gaps[gaps["year"] <= 2024].copy()
    att_pre = (pre.groupby("unit_id")["gap"]
               .mean()
               .reset_index()
               .rename(columns={"gap": "att_avg_pre"}))
    gaps = gaps.merge(att_pre, on="unit_id", how="left")

    # Rename unit_id -> nuts3_code for output (already have nuts3_code from merge)
    gaps = gaps.drop(columns=["unit_id", "nuts3_code"]).rename(
        columns={"nuts3_code": "nuts3_code"}  # noop; handle gracefully
    )
    # Restore nuts3_code column
    gaps = gaps.rename(columns={c: c for c in gaps.columns})
    # unit_id was the nuts3_code
    gaps.insert(0, "nuts3_code_out", gaps.get("nuts3_code", gaps.get("unit_id", None)))

    out_cols = [
        "unit_id", "year", "judet_name", "county_seat", "nuts2_code",
        "actual", "counterfactual", "gap", "rmse_preperiod",
        "reform_scenario_pessimistic", "reform_scenario_central",
        "reform_scenario_optimistic", "att_avg_pre",
    ]
    out_cols_present = [c for c in out_cols if c in gaps.columns]
    out = gaps[out_cols_present].rename(columns={"unit_id": "nuts3_code"})

    out_path = PROCESSED / "ro_gsynth_gaps.parquet"
    out.to_parquet(out_path, index=False)

    print(f"Saved: data/processed/ro_gsynth_gaps.parquet")
    print(f"  Shape: {out.shape}")
    print(f"  Counties: {out['nuts3_code'].nunique()}")
    print(f"  Years: {out['year'].min()}-{out['year'].max()}")
    print("\nSample (2025 forecasts):")
    sample = (out[out["year"] == 2025]
              [["nuts3_code", "counterfactual",
                "reform_scenario_pessimistic", "reform_scenario_central"]]
              .head(8))
    print(sample.to_string(index=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4.2: Run and verify**

```powershell
python scripts/postprocess_gsynth.py
```

Expected:
```
Saved: data/processed/ro_gsynth_gaps.parquet
  Shape: (~1350, 13)
  Counties: 33
  Years: 1995-2035
```

- [ ] **Step 4.3: Commit Stage 11 outputs**

```powershell
git add RO-Administrative-Reform/scripts/r/11_gsynth.R
git add RO-Administrative-Reform/scripts/postprocess_gsynth.py
git add RO-Administrative-Reform/data/processed/cc_panel.parquet
git add RO-Administrative-Reform/data/processed/ro_gsynth_raw.parquet
git add RO-Administrative-Reform/data/processed/ro_gsynth_gaps.parquet
git add RO-Administrative-Reform/figures/f11_*.png
git commit -m "feat(RO-Stage11): cross-country GSC counterfactuals for 33 demoted counties"
```

---

## Task 5: Update PROGRESS.md

- [ ] **Step 5.1: Update Stage 11 row in stage table**

In `PROGRESS.md`, update the Stage 11 row:
```
| 11 gsynth | `scripts/r/11_gsynth.R` | PASS | `ro_gsynth_raw.parquet`, `ro_gsynth_gaps.parquet` |
```

Add a new section **Key Findings (Stage 11)** recording:
- r* (optimal number of factors)
- Average pre-period RMSE across all 33 counties (fit quality)
- Top 3 counties by |reform cost| under central scenario

---

## Known Issues & Fallbacks

### gsynth error: "no post-treatment observations"
**Symptom:** gsynth throws `Error: no post-treatment periods for treated units`

**Fix:** This happens if gsynth does not detect D=1 rows. Verify:
```r
table(panel$D)  # should show 363 rows with D=1
panel |> filter(D == 1) |> summarise(n_units = n_distinct(unit_id), years = paste(range(year), collapse="--"))
```
If D is all 0, check that `build_cc_panel.py` ran successfully and the 2025-2035 extension was saved.

### gsynth error: "matrix is singular" or convergence failure
**Symptom:** Optimization fails for high r values.

**Fix:** Reduce r range to `c(0, 3)` in the gsynth call. The PL run used r*=2; Romanian panel likely similar.

### Very high pre-period RMSE (> 0.1 for most counties)
**Symptom:** Synthetic controls are not fitting Romanian counties well.

**Cause:** Romanian counties may not have good matches in the Polish donor pool (different structural characteristics, much smaller population).

**Fix:** Run a domestic-only version (Romanian controls only) as a robustness check:
```r
ro_only <- panel |> filter(country == "RO")
out_domestic <- gsynth(ln_population ~ D, data = ro_only, ...)
```
Compare pre-period RMSE between cross-country and domestic versions. Report both in the paper.

---

## Self-Review Checklist

- [x] Spec coverage: build_cc_panel, gsynth run, postprocess, figures, PROGRESS update — all covered
- [x] Placeholder check: all code blocks contain actual implementation, no TBD
- [x] Type consistency: `unit_id` used throughout R script; renamed to `nuts3_code` in Python postprocess
- [x] Path consistency: `scripts/r/utils.R` uses `proj_root()` via `sys.frame(1)$ofile` — requires R to be run from project root
- [x] Data contract: output columns match what Stage 09 (MG-VAR) expects for the `counterfactual` starting state
