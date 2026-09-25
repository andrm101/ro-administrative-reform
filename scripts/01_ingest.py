"""
Stage 01 -- Ingest Eurostat time-series data for Romanian NUTS3 panel.

Reads multi-year bulk-download TSV files from RO-Voting-Prediction/data/raw/eurostat/
(no re-download needed -- those files cover all countries and all years).

Variables extracted (NUTS3 for Romania, RO111-RO424, RO321):
  ln_population       : log(total population), from demo_r_pjanaggr3
  nat_change_rate     : natural growth rate per 1000, from demo_r_gind3 (NATGROWRT)
  net_migration_rate  : net migration rate per 1000, from demo_r_gind3 (CNMIGRATRT)
  unemployment        : long-term unemployment rate % -- NUTS2 level broadcast to NUTS3
                        (lfst_r_lfu3rt does not publish Romanian NUTS3; documented limitation)
  gva_per_empl        : GVA per employed person (EUR), from nama_10r_3gva + nama_10r_3empers

Year range: 1995-2024 (population); 2000-2024 (other indicators)
Output: data/processed/ro_eurostat_interim.parquet (long: nuts3_code x year x variables)

Data notes:
  - NUTS3 unemployment unavailable from Eurostat for Romania; NUTS2 values broadcast within region
  - GVA unit: CP_MEUR (current prices millions EUR); employment unit: THS (thousands persons)
  - gva_per_empl = (CP_MEUR * 1e6) / (THS * 1e3) = EUR per person (current prices)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EUROSTAT_RAW = ROOT.parent / "RO-Voting-Prediction" / "data" / "raw" / "eurostat"
OUT_DIR = ROOT / "data" / "processed"

# NUTS3 -> NUTS2 crosswalk (from RO-Voting-Prediction/scripts/constants.py)
NUTS3_NUTS2: dict[str, str] = {
    **{c: "RO11" for c in ["RO111","RO112","RO113","RO114","RO115","RO116"]},
    **{c: "RO12" for c in ["RO121","RO122","RO123","RO124","RO125","RO126"]},
    **{c: "RO21" for c in ["RO211","RO212","RO213","RO214","RO215","RO216"]},
    **{c: "RO22" for c in ["RO221","RO222","RO223","RO224","RO225","RO226"]},
    **{c: "RO31" for c in ["RO311","RO312","RO313","RO314","RO315","RO316","RO317"]},
    **{c: "RO32" for c in ["RO321","RO322"]},
    **{c: "RO41" for c in ["RO411","RO412","RO413","RO414","RO415"]},
    **{c: "RO42" for c in ["RO421","RO422","RO423","RO424"]},
}


def _strip_flag(val: str) -> float | None:
    """Parse '12345.6 p' -> 12345.6; ':' -> None."""
    v = str(val).strip()
    if v in (":", "", "n.a.", "na", "N/A"):
        return None
    m = re.match(r"^([\d.,\-]+)\s*[a-zA-Z]*$", v)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            return None
    return None


def _read_eurostat_wide(path: Path, geo_pattern: str = r"^RO\d{3}$") -> pd.DataFrame:
    """
    Read an Eurostat bulk-download TSV into tidy long format.
    geo_pattern: regex to filter rows by geo code.
    Returns columns: [dim_keys..., 'geo', 'year' (int), 'value' (float|None)]
    """
    try:
        raw = pd.read_csv(path, sep="\t", encoding="utf-8-sig", dtype=str,
                          keep_default_na=False)
    except Exception as exc:
        print(f"  [ERROR] Cannot read {path.name}: {exc}", file=sys.stderr)
        return pd.DataFrame()

    first_col = raw.columns[0]
    # Dimension names: "freq,unit,sex,age,geo\TIME_PERIOD" -> ["freq","unit","sex","age","geo"]
    dim_str = re.split(r"[\\]", first_col)[0]
    dim_names = [d.strip() for d in dim_str.split(",")]
    n_dims = len(dim_names)

    # Split first column on comma to extract dimension values
    splits = raw[first_col].str.split(",", expand=True)
    for i, name in enumerate(dim_names):
        if i < splits.shape[1]:
            raw[name] = splits[i].str.strip()

    geo_col = dim_names[-1]  # geo is always the last dimension
    ro_mask = raw[geo_col].str.match(geo_pattern, na=False)
    raw = raw[ro_mask].copy()
    if raw.empty:
        return pd.DataFrame()

    # Identify year columns
    year_map: dict[str, int] = {}
    for col in raw.columns:
        try:
            yr = int(str(col).strip())
            year_map[col] = yr
        except ValueError:
            pass

    if not year_map:
        return pd.DataFrame()

    records: list[dict] = []
    for _, row in raw.iterrows():
        base = {name: row[name] for name in dim_names}
        for col, yr in year_map.items():
            v = _strip_flag(row[col])
            records.append({**base, "year": yr, "value": v})

    return pd.DataFrame(records)


def ingest_population() -> pd.DataFrame:
    """
    demo_r_pjanaggr3: total population at NUTS3, annual.
    Filter: sex=T, age=TOTAL, unit=NR
    Returns: nuts3_code | year | ln_population
    """
    path = EUROSTAT_RAW / "demo_r_pjanaggr3_full.tsv"
    if not path.exists():
        print(f"  [WARN] {path.name} not found", file=sys.stderr)
        return pd.DataFrame()

    df = _read_eurostat_wide(path)
    if df.empty:
        return df

    mask = (df["sex"] == "T") & (df["age"] == "TOTAL") & (df["unit"] == "NR")
    df = df[mask].rename(columns={"geo": "nuts3_code"})
    df = df[["nuts3_code", "year", "value"]].dropna(subset=["value"])
    df["value"] = df["value"].astype(float)
    df = df[df["value"] > 0].copy()
    df["ln_population"] = np.log(df["value"])
    result = df[["nuts3_code", "year", "ln_population"]].copy()
    print(f"  population: {len(result):,} rows, {result['nuts3_code'].nunique()} units, "
          f"years {result['year'].min()}-{result['year'].max()}")
    return result


def ingest_demographic_indicators() -> pd.DataFrame:
    """
    demo_r_gind3: demographic indicators at NUTS3.
    Extracts NATGROWRT (natural growth rate per 1000) and CNMIGRATRT (net migration rate).
    Returns: nuts3_code | year | nat_change_rate | net_migration_rate
    """
    path = EUROSTAT_RAW / "demo_r_gind3_full.tsv"
    if not path.exists():
        print(f"  [WARN] {path.name} not found", file=sys.stderr)
        return pd.DataFrame()

    df = _read_eurostat_wide(path)
    if df.empty:
        return df

    df = df.rename(columns={"geo": "nuts3_code", "indic_de": "indicator"})
    available = sorted(df["indicator"].unique())
    print(f"  demo_r_gind3 available indicators: {available}")

    def _extract(indic: str, out_col: str, fallbacks: list[str]) -> pd.DataFrame:
        for code in [indic] + fallbacks:
            sub = df[df["indicator"] == code][["nuts3_code", "year", "value"]].dropna(
                subset=["value"]).copy()
            if not sub.empty:
                if code != indic:
                    print(f"    [{indic}] empty -- using fallback [{code}]")
                return sub.rename(columns={"value": out_col})
        print(f"    [WARN] {indic} and fallbacks not found", file=sys.stderr)
        return pd.DataFrame()

    nat = _extract("NATGROWRT", "nat_change_rate", fallbacks=["NATGROW_RT", "NATGROW"])
    mig = _extract("CNMIGRATRT", "net_migration_rate", fallbacks=["CNMIGRAT_RT", "CNMIGRAT"])

    if nat.empty and mig.empty:
        return pd.DataFrame()

    if nat.empty:
        result = mig
    elif mig.empty:
        result = nat
    else:
        result = nat.merge(mig, on=["nuts3_code", "year"], how="outer")

    print(f"  demographic indicators: {len(result):,} rows, "
          f"{result['nuts3_code'].nunique()} units, "
          f"years {result['year'].min()}-{result['year'].max()}")
    return result


def ingest_unemployment() -> pd.DataFrame:
    """
    lfst_r_lfu3rt: unemployment rate at NUTS2 (Romanian NUTS3 not published by Eurostat).
    Broadcasts NUTS2 value to all constituent NUTS3 units.
    Filter: isced11=TOTAL, sex=T, age=TOTAL, unit=PC
    Returns: nuts3_code | year | unemployment

    Documented limitation: within-region variation in unemployment not captured.
    """
    path = EUROSTAT_RAW / "lfst_r_lfu3rt_full.tsv"
    if not path.exists():
        print(f"  [WARN] {path.name} not found", file=sys.stderr)
        return pd.DataFrame()

    # Read NUTS2 level (4-char codes like RO11, RO12...)
    df = _read_eurostat_wide(path, geo_pattern=r"^RO\d{2}$")
    if df.empty:
        print("  [WARN] No NUTS2 unemployment data found for Romania", file=sys.stderr)
        return pd.DataFrame()

    df = df.rename(columns={"geo": "nuts2_code"})

    # Try best filter: isced11=TOTAL, sex=T, age=TOTAL, unit=PC
    for age_val in ("TOTAL", "Y15-74", "Y15-64"):
        mask = (
            (df.get("isced11", pd.Series("TOTAL", index=df.index)) == "TOTAL")
            & (df["sex"] == "T")
            & (df["age"] == age_val)
            & (df["unit"] == "PC")
        )
        sub = df[mask].copy()
        if not sub.empty:
            print(f"  unemployment filter: isced11=TOTAL, sex=T, age={age_val}, unit=PC (NUTS2)")
            break
    else:
        mask = (df["sex"] == "T") & (df["unit"] == "PC")
        sub = df[mask].copy()
        if sub.empty:
            print("  [WARN] No unemployment rows matched any filter", file=sys.stderr)
            return pd.DataFrame()
        print("  unemployment: fallback filter sex=T, unit=PC (NUTS2)")

    sub = sub[["nuts2_code", "year", "value"]].dropna(subset=["value"])
    sub["value"] = sub["value"].astype(float)
    sub = sub[sub["value"].between(0, 60)].copy()
    sub = sub.groupby(["nuts2_code", "year"])["value"].mean().reset_index()

    # Broadcast NUTS2 -> NUTS3
    nuts3_df = pd.DataFrame([
        {"nuts3_code": n3, "nuts2_code": n2}
        for n3, n2 in NUTS3_NUTS2.items()
    ])
    merged = nuts3_df.merge(sub, on="nuts2_code", how="left")
    merged = merged.rename(columns={"value": "unemployment"})
    result = merged[["nuts3_code", "year", "unemployment"]].dropna(subset=["unemployment"])

    print(f"  unemployment (NUTS2->NUTS3 broadcast): {len(result):,} rows, "
          f"{result['nuts3_code'].nunique()} units, "
          f"years {result['year'].min()}-{result['year'].max()}")
    return result


def ingest_gva() -> pd.DataFrame:
    """
    nama_10r_3gva (CP_MEUR, TOTAL) + nama_10r_3empers (THS, EMP, TOTAL) at NUTS3.
    Computes GVA per employed person as productivity proxy (no wage data at NUTS3).
    Returns: nuts3_code | year | gva_total_mn | employment_ths | gva_per_empl
    """
    gva_path = EUROSTAT_RAW / "nama_10r_3gva_full.tsv"
    emp_path = EUROSTAT_RAW / "nama_10r_3empers_full.tsv"

    # GVA: freq,unit,nace_r2,geo -- want unit=CP_MEUR, nace_r2=TOTAL
    if not gva_path.exists():
        print(f"  [WARN] {gva_path.name} not found", file=sys.stderr)
        return pd.DataFrame()
    gva_raw = _read_eurostat_wide(gva_path)
    if not gva_raw.empty:
        gva_raw = gva_raw.rename(columns={"geo": "nuts3_code"})
        gva_mask = (gva_raw["unit"] == "CP_MEUR") & (gva_raw["nace_r2"] == "TOTAL")
        gva = gva_raw[gva_mask][["nuts3_code", "year", "value"]].dropna(subset=["value"]).copy()
        gva["value"] = gva["value"].astype(float)
        gva = gva.rename(columns={"value": "gva_total_mn"})
        print(f"  GVA (CP_MEUR, TOTAL): {len(gva):,} rows, {gva['nuts3_code'].nunique()} units")
    else:
        print("  [WARN] GVA data empty after NUTS3 filter", file=sys.stderr)
        gva = pd.DataFrame()

    # Employment: freq,unit,wstatus,nace_r2,geo -- want unit=THS, wstatus=EMP, nace_r2=TOTAL
    if not emp_path.exists():
        print(f"  [WARN] {emp_path.name} not found", file=sys.stderr)
        return pd.DataFrame()
    emp_raw = _read_eurostat_wide(emp_path)
    if not emp_raw.empty:
        emp_raw = emp_raw.rename(columns={"geo": "nuts3_code"})
        emp_mask = (
            (emp_raw["unit"] == "THS")
            & (emp_raw["wstatus"] == "EMP")
            & (emp_raw["nace_r2"] == "TOTAL")
        )
        emp = emp_raw[emp_mask][["nuts3_code", "year", "value"]].dropna(subset=["value"]).copy()
        emp["value"] = emp["value"].astype(float)
        emp = emp[emp["value"] > 0]
        emp = emp.rename(columns={"value": "employment_ths"})
        print(f"  Employment (THS, EMP, TOTAL): {len(emp):,} rows, "
              f"{emp['nuts3_code'].nunique()} units")
    else:
        print("  [WARN] Employment data empty after NUTS3 filter", file=sys.stderr)
        emp = pd.DataFrame()

    if gva.empty or emp.empty:
        print("  [WARN] GVA or employment missing -- skipping gva_per_empl", file=sys.stderr)
        return pd.DataFrame()

    merged = gva.merge(emp, on=["nuts3_code", "year"], how="inner")
    # EUR per person = (MN_EUR * 1e6) / (THS_persons * 1e3)
    merged["gva_per_empl"] = (merged["gva_total_mn"] * 1e6) / (merged["employment_ths"] * 1e3)
    merged = merged[merged["gva_per_empl"] > 0]

    result = merged[["nuts3_code", "year", "gva_total_mn", "employment_ths", "gva_per_empl"]]
    print(f"  gva_per_empl: {len(result):,} rows, {result['nuts3_code'].nunique()} units, "
          f"years {result['year'].min()}-{result['year'].max()}")
    return result


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not EUROSTAT_RAW.exists():
        print(f"[ERROR] Source directory not found: {EUROSTAT_RAW}", file=sys.stderr)
        print("Ensure RO-Voting-Prediction project is at the same Sandbox level.",
              file=sys.stderr)
        sys.exit(1)

    print("=== Stage 01: Ingest Eurostat NUTS3 panel for Romania ===\n")

    print("-- Population (demo_r_pjanaggr3)")
    pop = ingest_population()

    print("\n-- Demographic indicators (demo_r_gind3)")
    demo = ingest_demographic_indicators()

    print("\n-- Unemployment (lfst_r_lfu3rt) [NUTS2 broadcast]")
    unemp = ingest_unemployment()

    print("\n-- GVA + Employment (nama_10r_3gva + nama_10r_3empers)")
    gva = ingest_gva()

    # Outer-merge all frames on nuts3_code x year
    frames = [f for f in [pop, demo, unemp, gva] if not f.empty]
    if not frames:
        print("[ERROR] No data ingested.", file=sys.stderr)
        sys.exit(1)

    merged = frames[0]
    for f in frames[1:]:
        merged = merged.merge(f, on=["nuts3_code", "year"], how="outer")

    # Restrict to Romanian NUTS3 codes and years 1995-2024
    merged = merged[merged["year"].between(1995, 2024)]
    merged = merged[merged["nuts3_code"].str.match(r"^RO\d{3}$", na=False)]
    merged = merged.sort_values(["nuts3_code", "year"]).reset_index(drop=True)

    out_path = OUT_DIR / "ro_eurostat_interim.parquet"
    merged.to_parquet(out_path, index=False)

    print(f"\n{'='*55}")
    print(f"Saved: {out_path.relative_to(ROOT)}")
    print(f"Shape: {merged.shape}")
    print(f"Units: {merged['nuts3_code'].nunique()}")
    print(f"Years: {merged['year'].min()}-{merged['year'].max()}")
    print("\nColumn coverage (non-null %):")
    for col in merged.columns:
        if col in ("nuts3_code", "year"):
            continue
        pct = merged[col].notna().mean()
        print(f"  {col:30s}: {pct:.0%}")


if __name__ == "__main__":
    main()
