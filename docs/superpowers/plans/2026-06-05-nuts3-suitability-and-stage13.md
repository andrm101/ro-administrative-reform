# MegaCampus NUTS3 Suitability + Stage 13 Innovation ROI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Downscale NUTS2 MegaCampus suitability scores to 42 Romanian NUTS3 counties using a vitality index + B-E industrial proxy, gate by Tier-1 threshold, then feed the result into Stage 13 to compute the Innovation Hub forecast path.

**Architecture:** `build_nuts3_suitability.py` reads four input files, computes a vitality index (OLS trends + levels, z-scored), ranks counties within NUTS2 regions, redistributes NUTS2 suitability ±20%, handles T4 via B-E employment share (D35 not present in source file; B-E/TOTAL is the best available industrial capacity proxy), clips scores to [0,1], and writes `ro_nuts3_suitability.parquet`. `13_innovation_roi.R` then reads `tier1_gate` / `tier1_types` from that parquet and applies type-specific Moretti agglomeration multipliers to the gsynth counterfactual path, writing the `innovation_hub` column into a copy of `ro_pvar_forecasts.parquet`.

**Tech Stack:** Python 3.x, pandas, scipy.stats, pyarrow (suitability script); R, readr, dplyr, tidyr (Stage 13 ROI script)

---

## Data Contracts Established

### Inputs

| File | Key columns used |
|---|---|
| `../EU-MegaCampus-Siting/data/gold/suitability_scores.parquet` | Index `nuts2_code`, `suitability_T1`…`suitability_T8` |
| `data/processed/ro_panel_judet.parquet` | `nuts3_code`, `nuts2_code`, `year`, `ln_gva_per_empl`, `net_migration_rate`, `nat_change_rate` |
| `data/processed/ro_treatment_cities.parquet` | `nuts3_code`, `judet_name`, `county_seat`, `nuts2_code` |
| `../RO-Voting-Prediction/data/raw/eurostat/nama_10r_3empers_full.tsv` | `wstatus=EMP`, `nace_r2=B-E` and `TOTAL`, `unit=THS`; NUTS3 codes `len==5` starting with `RO` |

**D35 availability note:** The Eurostat TSV contains no `D35` or `D` NACE code entries. NACE codes available for Romania are: `A`, `B-E`, `C`, `F`, `G-I`, `G-J`, `J`, `K`, `K-N`, `L`, `M_N`, `O-Q`, `O-U`, `R-U`, `TOTAL`. The T4 anchor therefore uses the `B-E / TOTAL` employment share (industry including utilities) as the best available NUTS3 industrial capacity proxy, flagged as `t4_anchor_source = "industry_b_e_proxy"`. This is directionally correct: Gorj (lignite), Hunedoara (hydro/industrial energy), and Constanța (port energy) rank high on B-E share.

### Outputs

| File | Rows | Key columns |
|---|---|---|
| `data/processed/ro_nuts3_suitability.parquet` | 42 | `nuts3_code`, `judet_name`, `county_seat`, `nuts2_code`, `vitality_gva_growth`, `vitality_migration_trend`, `vitality_nat_change`, `vitality_index`, `vitality_rank_within_region`, `d35_emp_share`, `d35_rank_within_region`, `t4_anchor_source`, `suitability_T1`…`suitability_T8`, `suitability_T4_adjusted`, `tier1_gate`, `tier1_types` |
| `data/processed/ro_nuts3_suitability.parquet` also feeds Stage 13 → writes `innovation_hub` into `ro_pvar_forecasts.parquet` |

### Region sizes (for rank normalization)
```
RO11: 6   RO12: 6   RO21: 6   RO22: 6
RO31: 7   RO32: 2   RO41: 5   RO42: 4
```
Single-county edge case: none (minimum region size = 2 for RO32).

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `scripts/build_nuts3_suitability.py` | CREATE | All steps: ingest → vitality → D35 proxy → redistribution → gate → write |
| `scripts/r/13_innovation_roi.R` | CREATE | Read suitability parquet, apply Moretti multipliers, write innovation_hub path |
| `data/processed/ro_nuts3_suitability.parquet` | OUTPUT | Written by suitability script |
| `data/processed/ro_pvar_forecasts_roi.parquet` | OUTPUT | Written by Stage 13 (copy of forecasts with innovation_hub populated) |

---

## Task 1: Scaffold the suitability script with imports and path constants

**Files:**
- Create: `scripts/build_nuts3_suitability.py`

- [ ] **Step 1: Create the file with header, imports, and path constants**

```python
"""
build_nuts3_suitability.py — NUTS3 MegaCampus investability scores for Romania.

Downscales EU-MegaCampus-Siting NUTS2 scores to 42 Romanian NUTS3 counties:
  1. Vitality index from ro_panel_judet (GVA growth trend + migration trend + nat change)
  2. Within-region rank normalization → ±20% redistribution of NUTS2 suitability
  3. T4 (Cleantech) anchor via B-E/TOTAL employment share (D35 not in source TSV)
  4. Tier-1 gate: any type >= 0.70 → tier1_gate = True
"""

from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import linregress

np.random.seed(42)

ROOT = Path(__file__).resolve().parents[1]  # RO-Administrative-Reform/
DATA_PROCESSED = ROOT / "data" / "processed"
SUITABILITY_PATH = ROOT.parent / "EU-MegaCampus-Siting" / "data" / "gold" / "suitability_scores.parquet"
PANEL_PATH = DATA_PROCESSED / "ro_panel_judet.parquet"
TREATMENT_PATH = DATA_PROCESSED / "ro_treatment_cities.parquet"
EMPERS_TSV = ROOT.parent / "RO-Voting-Prediction" / "data" / "raw" / "eurostat" / "nama_10r_3empers_full.tsv"
OUTPUT_PATH = DATA_PROCESSED / "ro_nuts3_suitability.parquet"

VITALITY_START = 2015
VITALITY_END = 2024
NAT_CHANGE_START = 2020

SUIT_TYPES = [f"T{k}" for k in range(1, 9)]
TIER1_THRESHOLD = 0.70
```

- [ ] **Step 2: Verify the file was created and is importable (no syntax errors)**

```powershell
cd "c:\Users\andre\Desktop\Sandbox\RO-Administrative-Reform"
python -c "import ast; ast.parse(open('scripts/build_nuts3_suitability.py').read()); print('Syntax OK')"
```

Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```powershell
git add RO-Administrative-Reform/scripts/build_nuts3_suitability.py
git commit -m "feat(RO): scaffold build_nuts3_suitability.py with paths and constants"
```

---

## Task 2: Load inputs and compute the vitality index

**Files:**
- Modify: `scripts/build_nuts3_suitability.py`

- [ ] **Step 1: Add `load_inputs()` function after the constants block**

```python
def load_inputs():
    """Load all four inputs; return metadata df and panel slice for vitality."""
    meta = pd.read_parquet(TREATMENT_PATH)[
        ["nuts3_code", "judet_name", "county_seat", "nuts2_code"]
    ].copy()
    panel = pd.read_parquet(PANEL_PATH)
    suit_nuts2 = pd.read_parquet(SUITABILITY_PATH)
    return meta, panel, suit_nuts2
```

- [ ] **Step 2: Add `compute_vitality_index(panel, meta)` function**

```python
def compute_vitality_index(panel: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """
    Compute vitality index from 2015-2024 panel:
      - GVA/employment OLS trend slope (z-scored)
      - Net migration rate OLS trend slope (z-scored)
      - Natural change rate mean 2020-2024 (z-scored)
    Equal-weight composite, then within-NUTS2 rank [0,1].
    """
    vit_period = panel[panel["year"].between(VITALITY_START, VITALITY_END)].copy()
    nc_period = panel[panel["year"].between(NAT_CHANGE_START, VITALITY_END)].copy()

    def ols_slope(df, variable):
        """Return OLS slope of variable ~ year per nuts3_code."""
        results = {}
        for code, grp in df.groupby("nuts3_code"):
            grp_clean = grp[["year", variable]].dropna()
            if len(grp_clean) >= 3:
                slope, *_ = linregress(grp_clean["year"], grp_clean[variable])
            else:
                slope = np.nan
            results[code] = slope
        return pd.Series(results, name=f"slope_{variable}")

    gva_slopes = ols_slope(vit_period, "ln_gva_per_empl")
    mig_slopes = ols_slope(vit_period, "net_migration_rate")
    nc_means = nc_period.groupby("nuts3_code")["nat_change_rate"].mean()

    vit = pd.DataFrame({
        "vitality_gva_growth_raw": gva_slopes,
        "vitality_migration_trend_raw": mig_slopes,
        "vitality_nat_change_raw": nc_means,
    })

    # Z-score each component across all 42 counties
    for raw_col, z_col in [
        ("vitality_gva_growth_raw", "vitality_gva_growth"),
        ("vitality_migration_trend_raw", "vitality_migration_trend"),
        ("vitality_nat_change_raw", "vitality_nat_change"),
    ]:
        mu = vit[raw_col].mean()
        sd = vit[raw_col].std(ddof=1)
        vit[z_col] = (vit[raw_col] - mu) / sd

    vit["vitality_index"] = vit[["vitality_gva_growth", "vitality_migration_trend", "vitality_nat_change"]].mean(axis=1)

    # Join nuts2_code for within-region rank
    vit = vit.join(meta.set_index("nuts3_code")[["nuts2_code"]])

    # Within-region rank normalized to [0, 1]
    def region_rank(grp):
        n = len(grp)
        ranks = grp["vitality_index"].rank(method="average") - 1
        denom = max(1, n - 1)
        grp["vitality_rank_within_region"] = ranks / denom
        return grp

    vit = vit.groupby("nuts2_code", group_keys=False).apply(region_rank)
    vit = vit.drop(columns=["vitality_gva_growth_raw", "vitality_migration_trend_raw", "vitality_nat_change_raw"])
    return vit.reset_index().rename(columns={"index": "nuts3_code"})
```

- [ ] **Step 3: Add a `__main__` block to test vitality output**

```python
if __name__ == "__main__":
    meta, panel, suit_nuts2 = load_inputs()
    print("Inputs loaded OK:", len(meta), "counties,", len(panel), "panel rows")
    vit = compute_vitality_index(panel, meta)
    print("Vitality index shape:", vit.shape)
    print(vit[["nuts3_code", "vitality_index", "vitality_rank_within_region"]].sort_values("vitality_rank_within_region", ascending=False).head(8).to_string(index=False))
```

- [ ] **Step 4: Run and verify**

```powershell
cd "c:\Users\andre\Desktop\Sandbox\RO-Administrative-Reform"
python scripts/build_nuts3_suitability.py
```

Expected: 42 rows with `vitality_rank_within_region` in [0, 1], no NaNs in any z-score column.

- [ ] **Step 5: Commit**

```powershell
git add RO-Administrative-Reform/scripts/build_nuts3_suitability.py
git commit -m "feat(RO): vitality index with within-region rank for NUTS3 suitability"
```

---

## Task 3: Parse B-E employment share for T4 anchor

**Files:**
- Modify: `scripts/build_nuts3_suitability.py`

- [ ] **Step 1: Add `compute_be_employment_share()` function**

```python
def compute_be_employment_share() -> pd.DataFrame:
    """
    Parse nama_10r_3empers_full.tsv for Romanian NUTS3 B-E and TOTAL employment.
    D35 (electricity/gas/steam) is not present in this Eurostat release.
    B-E (industry incl. utilities) / TOTAL is the best available industrial
    capacity proxy for T4 Cleantech; flagged as 't4_anchor_source=industry_b_e_proxy'.

    Returns DataFrame with columns: nuts3_code, d35_emp_share, t4_anchor_source.
    """
    with open(EMPERS_TSV, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.strip().split("\n")
    header_parts = lines[0].split("\t")
    years = [h.strip() for h in header_parts[1:]]

    def parse_rows(nace_filter):
        rows = {}
        for line in lines[1:]:
            parts = line.split("\t")
            keys = parts[0].split(",")
            if len(keys) < 5:
                continue
            freq, unit, wstatus, nace_r2, geo = keys[0], keys[1], keys[2], keys[3], keys[4]
            if nace_r2 != nace_filter or wstatus != "EMP" or unit != "THS":
                continue
            if not (geo.startswith("RO") and len(geo) == 5):
                continue
            vals = {}
            for yr, raw in zip(years, parts[1:]):
                v = raw.strip().rstrip(" bcdeprsuz")
                vals[int(yr)] = float(v) if v not in (":", "") else np.nan
            rows[geo] = vals
        return rows

    be_rows = parse_rows("B-E")
    total_rows = parse_rows("TOTAL")

    result = []
    for nuts3 in be_rows:
        if nuts3 not in total_rows:
            continue
        # Use most recent year with non-missing data for both
        be_vals = be_rows[nuts3]
        tot_vals = total_rows[nuts3]
        for yr in sorted(be_vals.keys(), reverse=True):
            be_v = be_vals.get(yr)
            tot_v = tot_vals.get(yr)
            if be_v is not None and tot_v is not None and not np.isnan(be_v) and not np.isnan(tot_v) and tot_v > 0:
                result.append({
                    "nuts3_code": nuts3,
                    "d35_emp_share": be_v / tot_v,
                    "t4_anchor_source": "industry_b_e_proxy",
                })
                break

    df = pd.DataFrame(result)
    if df.empty:
        return pd.DataFrame(columns=["nuts3_code", "d35_emp_share", "t4_anchor_source"])
    return df
```

- [ ] **Step 2: Update `__main__` to test B-E extraction**

Replace the `__main__` block with:

```python
if __name__ == "__main__":
    meta, panel, suit_nuts2 = load_inputs()
    print("Inputs loaded:", len(meta), "counties")

    vit = compute_vitality_index(panel, meta)
    print("Vitality OK:", vit.shape)

    be = compute_be_employment_share()
    print("B-E rows:", len(be))
    print(be.sort_values("d35_emp_share", ascending=False).head(8).to_string(index=False))
```

- [ ] **Step 3: Run and verify**

```powershell
python scripts/build_nuts3_suitability.py
```

Expected: 42 B-E rows with `d35_emp_share` values roughly 0.15–0.45. Gorj (RO412) and Hunedoara (RO423) should appear near the top.

- [ ] **Step 4: Commit**

```powershell
git add RO-Administrative-Reform/scripts/build_nuts3_suitability.py
git commit -m "feat(RO): B-E/TOTAL employment share as T4 industrial proxy (D35 absent from TSV)"
```

---

## Task 4: Redistribute NUTS2 suitability to NUTS3 and apply T4 D35 formula

**Files:**
- Modify: `scripts/build_nuts3_suitability.py`

- [ ] **Step 1: Add `compute_d35_rank(be_df, meta_vit)` helper for within-region B-E rank**

```python
def compute_d35_rank(be_df: pd.DataFrame, meta_vit: pd.DataFrame) -> pd.DataFrame:
    """
    Compute within-region rank of d35_emp_share for T4 weight.
    Merges nuts2_code from meta_vit. Counties missing B-E share get fallback = vitality_rank.
    """
    df = meta_vit[["nuts3_code", "nuts2_code", "vitality_rank_within_region"]].merge(
        be_df[["nuts3_code", "d35_emp_share", "t4_anchor_source"]], on="nuts3_code", how="left"
    )

    def region_d35_rank(grp):
        n = grp["d35_emp_share"].notna().sum()
        if n <= 1:
            grp["d35_rank_within_region"] = np.nan
        else:
            ranks = grp["d35_emp_share"].rank(method="average", na_option="keep") - 1
            denom = max(1, grp["d35_emp_share"].notna().sum() - 1)
            grp["d35_rank_within_region"] = ranks / denom
        return grp

    df = df.groupby("nuts2_code", group_keys=False).apply(region_d35_rank)

    # Fill fallback where d35_emp_share is missing
    mask_missing = df["d35_emp_share"].isna()
    df.loc[mask_missing, "d35_rank_within_region"] = df.loc[mask_missing, "vitality_rank_within_region"]
    df.loc[mask_missing, "t4_anchor_source"] = "vitality_fallback"
    df["t4_anchor_source"] = df["t4_anchor_source"].fillna("industry_b_e_proxy")

    return df
```

- [ ] **Step 2: Add `redistribute_suitability(meta_vit_d35, suit_nuts2)` function**

```python
def redistribute_suitability(meta_vit_d35: pd.DataFrame, suit_nuts2: pd.DataFrame) -> pd.DataFrame:
    """
    Broadcast NUTS2 suitability to NUTS3 with ±20% vitality-rank redistribution.
    T4 uses 60% d35_rank + 40% vitality_rank composite before redistribution.
    All scores clipped to [0, 1].
    """
    ro_suit = suit_nuts2.loc[suit_nuts2["country_code"] == "RO", [f"suitability_{t}" for t in SUIT_TYPES]].copy()

    df = meta_vit_d35.merge(ro_suit, left_on="nuts2_code", right_index=True, how="left")

    # General formula for T1-T3, T5-T8
    for t in SUIT_TYPES:
        if t == "T4":
            continue
        col_nuts2 = f"suitability_{t}"
        df[col_nuts2] = (
            df[col_nuts2] * (1.0 + 0.4 * (df["vitality_rank_within_region"] - 0.5))
        ).clip(0.0, 1.0)

    # T4: composite weight 60% d35_rank + 40% vitality_rank
    df["t4_weight"] = 0.6 * df["d35_rank_within_region"] + 0.4 * df["vitality_rank_within_region"]
    df["suitability_T4_adjusted"] = (
        df["suitability_T4"] * (1.0 + 0.4 * (df["t4_weight"] - 0.5))
    ).clip(0.0, 1.0)
    # Overwrite suitability_T4 with adjusted version in the main columns
    df["suitability_T4"] = df["suitability_T4_adjusted"]

    return df
```

- [ ] **Step 3: Add `apply_tier1_gate(df)` function**

```python
def apply_tier1_gate(df: pd.DataFrame) -> pd.DataFrame:
    """Flag counties where any adjusted suitability score >= 0.70."""
    type_cols = [f"suitability_{t}" for t in SUIT_TYPES]
    df["tier1_gate"] = df[type_cols].ge(TIER1_THRESHOLD).any(axis=1)
    df["tier1_types"] = df[type_cols].apply(
        lambda row: "|".join(t for t, v in zip(SUIT_TYPES, row) if v >= TIER1_THRESHOLD),
        axis=1,
    )
    df.loc[df["tier1_types"] == "", "tier1_types"] = ""
    return df
```

- [ ] **Step 4: Add `build_output(df)` to select and order final columns**

```python
def build_output(df: pd.DataFrame) -> pd.DataFrame:
    """Select final output columns in spec order."""
    suit_cols = [f"suitability_{t}" for t in SUIT_TYPES]
    cols = (
        ["nuts3_code", "judet_name", "county_seat", "nuts2_code"]
        + ["vitality_gva_growth", "vitality_migration_trend", "vitality_nat_change",
           "vitality_index", "vitality_rank_within_region"]
        + ["d35_emp_share", "d35_rank_within_region", "t4_anchor_source"]
        + suit_cols
        + ["suitability_T4_adjusted", "t4_weight", "tier1_gate", "tier1_types"]
    )
    return df[cols].reset_index(drop=True)
```

- [ ] **Step 5: Commit**

```powershell
git add RO-Administrative-Reform/scripts/build_nuts3_suitability.py
git commit -m "feat(RO): NUTS2->NUTS3 redistribution and T4 D35 formula"
```

---

## Task 5: Wire main() and write output parquet

**Files:**
- Modify: `scripts/build_nuts3_suitability.py`

- [ ] **Step 1: Add `main()` function and update `__main__` block**

```python
def main():
    meta, panel, suit_nuts2 = load_inputs()

    vit = compute_vitality_index(panel, meta)

    be = compute_be_employment_share()

    meta_vit = meta.merge(vit, on="nuts3_code", how="left")
    # Drop duplicate nuts2_code from vit (already in meta_vit via meta)
    meta_vit = meta_vit.loc[:, ~meta_vit.columns.duplicated()]

    meta_vit_d35 = compute_d35_rank(be, meta_vit)

    df = redistribute_suitability(meta_vit_d35, suit_nuts2)
    df = apply_tier1_gate(df)
    out = build_output(df)

    out.to_parquet(OUTPUT_PATH, index=False)
    print(f"Written: {OUTPUT_PATH}  ({len(out)} rows x {len(out.columns)} columns)")
    print()
    print("Tier-1 counties:", out[out["tier1_gate"]]["nuts3_code"].tolist())
    print("T4 anchor sources:", out["t4_anchor_source"].value_counts().to_dict())
    print()
    print(out[["nuts3_code", "judet_name", "tier1_gate", "tier1_types"]].to_string(index=False))
    return out


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full script and verify output**

```powershell
cd "c:\Users\andre\Desktop\Sandbox\RO-Administrative-Reform"
python scripts/build_nuts3_suitability.py
```

Expected output indicators:
- "Written: ...ro_nuts3_suitability.parquet  (42 rows x 20 columns)"  
- T4 anchor sources: `{"industry_b_e_proxy": 42}` (or close; vitality_fallback only if B-E missing)
- Tier-1 counties listed (should be non-empty — RO32 Bucharest region scores highest on T1/T2)
- No NaNs in `vitality_index`, `vitality_rank_within_region`, `suitability_T1`–`T8`

- [ ] **Step 3: Spot-check parquet schema**

```powershell
python -c "
import pandas as pd, sys
sys.stdout.reconfigure(encoding='utf-8')
df = pd.read_parquet('data/processed/ro_nuts3_suitability.parquet')
print(df.dtypes)
print()
print('NaN counts:')
print(df.isna().sum())
print()
print('Suitability ranges:')
for c in [col for col in df.columns if col.startswith('suitability')]:
    print(f'  {c}: [{df[c].min():.3f}, {df[c].max():.3f}]')
print()
print('tier1_gate counts:', df['tier1_gate'].value_counts().to_dict())
"
```

Expected: all suitability columns in [0, 1]; `tier1_gate` has True for at least a few counties (Romanian NUTS2 T4 scores range 0.21–0.83, so after redistribution some will cross 0.70).

- [ ] **Step 4: Commit**

```powershell
git add RO-Administrative-Reform/scripts/build_nuts3_suitability.py
git add RO-Administrative-Reform/data/processed/ro_nuts3_suitability.parquet
git commit -m "feat(RO): complete build_nuts3_suitability.py -- 42 NUTS3 investability scores"
```

---

## Task 6: Stage 13 — Innovation ROI R script

**Files:**
- Create: `scripts/r/13_innovation_roi.R`

**Context:** The MG-VAR forecasts (`ro_pvar_forecasts.parquet`) contain `path` values `status_quo` and `counterfactual`; `innovation_hub` is currently absent. Stage 13 adds it for counties with `tier1_gate = TRUE`, using Moretti-style agglomeration multipliers per ecosystem type.

**Moretti multipliers (from VISION.md Phase 3 logic):**
| Type | Description | Annual GDP uplift above counterfactual |
|---|---|---|
| T1 | AI/ML Hub | +2.5% p.a. |
| T2 | Biotech/Life Sciences | +2.0% p.a. |
| T3 | Advanced Manufacturing | +1.5% p.a. |
| T4 | Cleantech | +1.2% p.a. |
| T5 | Hyperscale Data Center | +1.0% p.a. |
| T6 | Creative Economy Hub | +0.8% p.a. |
| T7 | Agri-food Innovation | +0.7% p.a. |
| T8 | Logistics/Mobility | +0.6% p.a. |

Multiplier is applied as a compound growth adjustment on `ln_population` path starting at the reform year (2025), ramping linearly from 0 to full effect over 5 years, then flat.

- [ ] **Step 1: Create `scripts/r/13_innovation_roi.R`**

```r
# 13_innovation_roi.R
# Stage 13: Innovation Hub forecast path for demoted Romanian counties.
# Reads ro_nuts3_suitability.parquet (tier1_gate, tier1_types) and
# ro_pvar_forecasts.parquet (status_quo / counterfactual paths).
# Produces ro_pvar_forecasts_roi.parquet with innovation_hub path added.

library(arrow)
library(dplyr)
library(tidyr)
library(readr)
library(stringr)

set.seed(42)

ROOT <- here::here()  # RO-Administrative-Reform/
DATA_PROC <- file.path(ROOT, "data", "processed")

SUIT_PATH    <- file.path(DATA_PROC, "ro_nuts3_suitability.parquet")
FCST_PATH    <- file.path(DATA_PROC, "ro_pvar_forecasts.parquet")
OUTPUT_PATH  <- file.path(DATA_PROC, "ro_pvar_forecasts_roi.parquet")

REFORM_YEAR  <- 2025
RAMP_YEARS   <- 5   # years over which multiplier ramps from 0 to full effect

# Annual GDP/population ln-uplift above counterfactual, per ecosystem type
MORETTI_MULTIPLIERS <- c(
  T1 = 0.025,  # AI/ML hub
  T2 = 0.020,  # Biotech
  T3 = 0.015,  # Advanced manufacturing
  T4 = 0.012,  # Cleantech
  T5 = 0.010,  # Hyperscale data centre
  T6 = 0.008,  # Creative economy
  T7 = 0.007,  # Agri-food innovation
  T8 = 0.006   # Logistics/mobility
)

# ── Load inputs ────────────────────────────────────────────────────────────────
suit <- read_parquet(SUIT_PATH) |>
  select(nuts3_code, tier1_gate, tier1_types)

fcst <- read_parquet(FCST_PATH)

stopifnot(nrow(suit) == 42)
cat("Forecast rows:", nrow(fcst), "\n")
cat("Variables:", paste(unique(fcst$variable), collapse = ", "), "\n")
cat("Paths present:", paste(unique(fcst$path), collapse = ", "), "\n")

# ── Determine max multiplier per county (highest-scoring Tier-1 type) ──────────
get_max_multiplier <- function(tier1_types_str) {
  if (is.na(tier1_types_str) || tier1_types_str == "") return(NA_real_)
  types <- str_split(tier1_types_str, "\\|")[[1]]
  mults <- MORETTI_MULTIPLIERS[types]
  mults <- mults[!is.na(mults)]
  if (length(mults) == 0) return(NA_real_)
  max(mults)
}

suit <- suit |>
  mutate(
    annual_uplift = sapply(tier1_types, get_max_multiplier),
    dominant_type = sapply(tier1_types, function(x) {
      if (is.na(x) || x == "") return(NA_character_)
      types <- str_split(x, "\\|")[[1]]
      mults <- MORETTI_MULTIPLIERS[types]
      names(mults)[which.max(mults)]
    })
  )

cat("Tier-1 counties:", sum(suit$tier1_gate, na.rm = TRUE), "\n")
cat("Uplift range:", range(suit$annual_uplift, na.rm = TRUE), "\n")

# ── Build innovation_hub path ──────────────────────────────────────────────────
counterfactual_rows <- fcst |>
  filter(path == "counterfactual") |>
  left_join(suit, by = "nuts3_code")

# For counties without Tier-1: innovation_hub = counterfactual (no uplift)
innovation_rows <- counterfactual_rows |>
  mutate(
    ramp_factor = case_when(
      !tier1_gate | is.na(annual_uplift) ~ 0,
      year < REFORM_YEAR ~ 0,
      year >= REFORM_YEAR & year < REFORM_YEAR + RAMP_YEARS ~
        annual_uplift * (year - REFORM_YEAR + 1) / RAMP_YEARS,
      TRUE ~ annual_uplift
    ),
    # Apply only to ln_population (primary outcome); pass-through for others
    value = if_else(
      variable == "ln_population",
      value + ramp_factor * (year - REFORM_YEAR + 1),
      value
    ),
    # Uncertainty bands widen slightly for innovation path (5% expansion)
    lo80 = if_else(variable == "ln_population", lo80 - abs(value - lo80) * 0.05, lo80),
    hi80 = if_else(variable == "ln_population", hi80 + abs(hi80 - value) * 0.05, hi80),
    lo95 = if_else(variable == "ln_population", lo95 - abs(value - lo95) * 0.05, lo95),
    hi95 = if_else(variable == "ln_population", hi95 + abs(hi95 - value) * 0.05, hi95),
    path = "innovation_hub"
  ) |>
  select(-tier1_gate, -tier1_types, -annual_uplift, -dominant_type, -ramp_factor)

# ── Combine and write ──────────────────────────────────────────────────────────
fcst_out <- bind_rows(fcst, innovation_rows) |>
  arrange(nuts3_code, variable, path, year)

write_parquet(fcst_out, OUTPUT_PATH)
cat("Written:", OUTPUT_PATH, "\n")
cat("Rows:", nrow(fcst_out), "(was", nrow(fcst), "+ added", nrow(innovation_rows), "innovation_hub rows)\n")
cat("Paths now:", paste(unique(fcst_out$path), collapse = ", "), "\n")

# ── Summary table ──────────────────────────────────────────────────────────────
suit |>
  select(nuts3_code, tier1_gate, tier1_types, annual_uplift, dominant_type) |>
  arrange(desc(annual_uplift)) |>
  print(n = 42)
```

- [ ] **Step 2: Run Stage 13**

```powershell
cd "c:\Users\andre\Desktop\Sandbox\RO-Administrative-Reform"
Rscript scripts/r/13_innovation_roi.R
```

Expected:
- "Tier-1 counties: N" (some positive number)
- "Written: ...ro_pvar_forecasts_roi.parquet"
- Paths now: `status_quo, counterfactual, innovation_hub`

- [ ] **Step 3: Verify parquet output**

```powershell
python -c "
import pandas as pd
df = pd.read_parquet('data/processed/ro_pvar_forecasts_roi.parquet')
print('Shape:', df.shape)
print('Paths:', df['path'].value_counts().to_dict())
print('Variables:', df['variable'].unique().tolist())
inn = df[df['path']=='innovation_hub']
print('Innovation hub rows:', len(inn))
print('Sample innovation_hub ln_population 2030:')
print(inn[(inn['variable']=='ln_population') & (inn['year']==2030)][['nuts3_code','value','lo80','hi80']].head(8).to_string(index=False))
"
```

- [ ] **Step 4: Commit**

```powershell
git add RO-Administrative-Reform/scripts/r/13_innovation_roi.R
git add RO-Administrative-Reform/data/processed/ro_pvar_forecasts_roi.parquet
git commit -m "feat(RO-Stage13): Innovation ROI -- Moretti multipliers + innovation_hub forecast path"
```

---

## Task 7: Update PROGRESS.md

**Files:**
- Modify: `RO-Administrative-Reform/PROGRESS.md`

- [ ] **Step 1: Update stage table and processed parquets section**

In the Stage Status table, update:
- MegaCampus NUTS3 suitability row: change `NOT STARTED` → `PASS`; note key output `ro_nuts3_suitability.parquet`
- Stage 13 row: change `NOT STARTED` → `PASS`; note output `ro_pvar_forecasts_roi.parquet`

In the Processed Parquets section, add:
```
  ro_nuts3_suitability.parquet   (42 rows; 20 columns; vitality + T1-T8 NUTS3 scores)
  ro_pvar_forecasts_roi.parquet  (3 paths: status_quo / counterfactual / innovation_hub)
```

In the "Next stages" section, advance priority to Stage 08 LP-IRFs and Stage 10 SDiD.

- [ ] **Step 2: Commit**

```powershell
git add RO-Administrative-Reform/PROGRESS.md
git commit -m "docs(RO): update PROGRESS.md after Stage 13 and NUTS3 suitability PASS"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Vitality index: GVA OLS slope + migration OLS slope + nat change mean, z-scored, equal weight → Task 2
- [x] Within-region rank [0,1] → Task 2
- [x] General redistribution formula ×(1 + 0.4×(rank − 0.5)) → Task 4
- [x] T4 60% D35/40% vitality weight → Task 4 (using B-E as D35 proxy; documented)
- [x] Fallback to vitality_fallback when D35 missing → Task 3 + 4
- [x] Clip to [0, 1] → Task 4 `.clip(0.0, 1.0)`
- [x] tier1_gate ≥ 0.70 → Task 4
- [x] tier1_types pipe-separated → Task 4
- [x] Output schema per spec → Task 5 `build_output()`
- [x] Stage 13 reads tier1_gate + tier1_types → Task 6
- [x] Moretti multipliers per type → Task 6
- [x] innovation_hub path written to forecasts → Task 6
- [x] PROGRESS.md updated → Task 7

**D35 deviation documented:** The spec requests `nace_r2=D35` from `nama_10r_3empers_full.tsv`. This code does not exist in the file (verified: 0 matching rows across all 61,680 lines). The B-E aggregate (industry + utilities + manufacturing) is used as the industrial capacity proxy and flagged `t4_anchor_source = "industry_b_e_proxy"`. Per spec fallback, if B-E is also missing, `vitality_fallback` applies.

**Type consistency check:** `nuts3_code` is `str` throughout all functions. `vitality_rank_within_region` and `d35_rank_within_region` are float [0,1]. `tier1_gate` is bool. All suitability columns are float clipped [0,1]. Stage 13 merges on `nuts3_code` (str, matches forecast parquet). ✓
