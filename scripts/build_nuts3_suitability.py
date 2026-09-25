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


def load_inputs():
    """Load all four inputs; return metadata df and panel slice for vitality."""
    meta = pd.read_parquet(TREATMENT_PATH)[
        ["nuts3_code", "judet_name", "county_seat", "nuts2_code"]
    ].copy()
    panel = pd.read_parquet(PANEL_PATH)
    suit_nuts2 = pd.read_parquet(SUITABILITY_PATH)
    return meta, panel, suit_nuts2


def compute_vitality_index(panel: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """
    Compute vitality index from 2015-2024 panel:
      - GVA/employment OLS trend slope (z-scored)
      - Net migration rate OLS trend slope (z-scored)
      - Natural change rate mean 2020-2024 (z-scored)
    Equal-weight composite, then within-NUTS2 rank [0, 1].
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

    vit = vit.groupby("nuts2_code", group_keys=False).apply(region_rank, include_groups=False)
    vit = vit.drop(columns=["vitality_gva_growth_raw", "vitality_migration_trend_raw", "vitality_nat_change_raw"])
    return vit.reset_index().rename(columns={"index": "nuts3_code"})


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

    df = df.groupby("nuts2_code", group_keys=False).apply(region_d35_rank, include_groups=False)

    # Fill fallback where d35_emp_share is missing
    mask_missing = df["d35_emp_share"].isna()
    df.loc[mask_missing, "d35_rank_within_region"] = df.loc[mask_missing, "vitality_rank_within_region"]
    df.loc[mask_missing, "t4_anchor_source"] = "vitality_fallback"
    df["t4_anchor_source"] = df["t4_anchor_source"].fillna("industry_b_e_proxy")

    return df


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


def main():
    meta, panel, suit_nuts2 = load_inputs()

    vit = compute_vitality_index(panel, meta)

    be = compute_be_employment_share()

    meta_vit = meta.merge(vit, on="nuts3_code", how="left")
    # Drop duplicate nuts2_code from vit (already in meta_vit via meta)
    meta_vit = meta_vit.loc[:, ~meta_vit.columns.duplicated()]

    meta_vit_d35 = compute_d35_rank(be, meta_vit)
    # Re-attach columns that groupby.apply(include_groups=False) drops
    # (nuts2_code, judet_name, county_seat, vitality columns)
    passthrough_cols = [
        "nuts3_code", "judet_name", "county_seat", "nuts2_code",
        "vitality_gva_growth", "vitality_migration_trend", "vitality_nat_change",
        "vitality_index",
    ]
    meta_vit_d35 = meta_vit[passthrough_cols].merge(
        meta_vit_d35, on="nuts3_code", how="left"
    )

    df = redistribute_suitability(meta_vit_d35, suit_nuts2)
    df = apply_tier1_gate(df)
    out = build_output(df)

    out.to_parquet(OUTPUT_PATH, index=False)
    print(f"Written: {OUTPUT_PATH}  ({len(out)} rows x {len(out.columns)} columns)")
    print()
    print("Tier-1 counties:", out[out["tier1_gate"]]["nuts3_code"].tolist())
    print("T4 anchor sources:", out["t4_anchor_source"].value_counts().to_dict())
    print()
    summary = out[["nuts3_code", "judet_name", "tier1_gate", "tier1_types"]].to_string(index=False)
    import sys
    sys.stdout.buffer.write((summary + "\n").encode("utf-8", errors="replace"))
    return out


if __name__ == "__main__":
    main()
