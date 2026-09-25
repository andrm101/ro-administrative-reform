"""
Export RO dashboard JSON from processed parquets.
Run from project root: python scripts/export_to_json_ro.py

Outputs (data/dashboard/):
  regions.json       — 33 treated counties, GSC series, reform scenarios
  forecasts.json     — 3-path MG-VAR fan chart per county
  suitability.json   — T1-T8 scores for all 42 counties
  lp_irfs.json       — LP IRF coefficients
  sdid_estimates.json — SDiD ATT estimates
  eventstudy.json    — TWFE event-study coefficients
  summary.json       — aggregate KPIs
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "data" / "dashboard"
OUT.mkdir(parents=True, exist_ok=True)


def _safe(val):
    if val is None:
        return None
    if isinstance(val, float) and np.isnan(val):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, bool):
        return bool(val)
    return val


def write_json(obj, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), default=_safe)
    print(f"  {path.name:<30} {path.stat().st_size / 1024:>7.1f} KB")


# ── regions.json ──────────────────────────────────────────────────────────────

def export_regions() -> None:
    gaps = pd.read_parquet(PROCESSED / "ro_gsynth_gaps.parquet")
    suit = pd.read_parquet(PROCESSED / "ro_nuts3_suitability.parquet").set_index("nuts3_code")

    # Compute innovation uplift at 2040 from pvar_forecasts_roi
    fcst = pd.read_parquet(PROCESSED / "ro_pvar_forecasts_roi.parquet")
    fcst_2040 = fcst[(fcst["year"] == 2040) & (fcst["variable"] == "ln_population")]
    uplift_map: dict[str, float | None] = {}
    for nuts3, grp in fcst_2040.groupby("nuts3_code"):
        ih = grp.loc[grp["path"] == "innovation_hub", "value"]
        sq = grp.loc[grp["path"] == "status_quo", "value"]
        if not ih.empty and not sq.empty:
            diff = float(ih.iloc[0]) - float(sq.iloc[0])
            uplift_map[str(nuts3)] = round((np.exp(diff) - 1) * 100, 2)
        else:
            uplift_map[str(nuts3)] = None

    regions = []
    for nuts3, grp in gaps.groupby("nuts3_code"):
        nuts3 = str(nuts3)
        row_suit = suit.loc[nuts3] if nuts3 in suit.index else {}
        att = _safe(grp["att_avg_pre"].iloc[0])
        reform_cost_pct = round(float(att) * 100, 2) if att is not None else None

        vitality = _safe(row_suit.get("vitality_index")) if hasattr(row_suit, "get") else None
        tier1_gate = bool(row_suit.get("tier1_gate", False)) if hasattr(row_suit, "get") else False
        tier1_types = str(row_suit.get("tier1_types", "")) if hasattr(row_suit, "get") else ""

        series = [
            {
                "year": int(r["year"]),
                "actual": _safe(r["actual"]),
                "counterfactual": _safe(r["counterfactual"]),
                "gap": _safe(r["gap"]),
            }
            for _, r in grp.sort_values("year").iterrows()
        ]

        regions.append({
            "nuts3_code": nuts3,
            "judet_name": str(grp["judet_name"].iloc[0]),
            "county_seat": str(grp["county_seat"].iloc[0]),
            "nuts2_code": str(grp["nuts2_code"].iloc[0]),
            "att_avg_pre": att,
            "reform_cost_pct": reform_cost_pct,
            "reform_scenario_pessimistic": _safe(grp["reform_scenario_pessimistic"].iloc[0]),
            "reform_scenario_central": _safe(grp["reform_scenario_central"].iloc[0]),
            "reform_scenario_optimistic": _safe(grp["reform_scenario_optimistic"].iloc[0]),
            "vitality_index": vitality,
            "tier1_gate": tier1_gate,
            "tier1_types": tier1_types,
            "innovation_uplift_pct_2040": uplift_map.get(nuts3),
            "counterfactualSeries": series,
        })

    write_json(regions, OUT / "regions.json")


# ── forecasts.json ────────────────────────────────────────────────────────────

def export_forecasts() -> None:
    pvar = pd.read_parquet(PROCESSED / "ro_pvar_forecasts_roi.parquet")
    out = []
    for nuts3, grp in pvar.groupby("nuts3_code"):
        county_name = str(grp["county_name"].iloc[0])
        forecasts: dict = {}
        for (var, path), sub in grp.groupby(["variable", "path"]):
            sub = sub.sort_values("year")
            forecasts.setdefault(str(var), {})[str(path)] = [
                {
                    "year": int(r["year"]),
                    "value": _safe(r["value"]),
                    "lo80": _safe(r["lo80"]),
                    "hi80": _safe(r["hi80"]),
                    "lo95": _safe(r["lo95"]),
                    "hi95": _safe(r["hi95"]),
                }
                for _, r in sub.iterrows()
            ]
        out.append({"nuts3_code": str(nuts3), "county_name": county_name, "forecasts": forecasts})
    write_json(out, OUT / "forecasts.json")


# ── suitability.json ──────────────────────────────────────────────────────────

def export_suitability() -> None:
    df = pd.read_parquet(PROCESSED / "ro_nuts3_suitability.parquet")
    records = []
    for _, r in df.iterrows():
        records.append({
            "nuts3_code": str(r["nuts3_code"]),
            "judet_name": str(r["judet_name"]),
            "county_seat": str(r["county_seat"]),
            "nuts2_code": str(r["nuts2_code"]),
            "vitality_index": _safe(r["vitality_index"]),
            "vitality_rank_within_region": _safe(r["vitality_rank_within_region"]),
            "suitability_T1": _safe(r["suitability_T1"]),
            "suitability_T2": _safe(r["suitability_T2"]),
            "suitability_T3": _safe(r["suitability_T3"]),
            "suitability_T4": _safe(r["suitability_T4"]),
            "suitability_T5": _safe(r["suitability_T5"]),
            "suitability_T6": _safe(r["suitability_T6"]),
            "suitability_T7": _safe(r["suitability_T7"]),
            "suitability_T8": _safe(r["suitability_T8"]),
            "suitability_T4_adjusted": _safe(r["suitability_T4_adjusted"]),
            "tier1_gate": bool(r["tier1_gate"]),
            "tier1_types": str(r["tier1_types"]),
            "t4_anchor_source": str(r["t4_anchor_source"]),
        })
    write_json(records, OUT / "suitability.json")


# ── lp_irfs.json ──────────────────────────────────────────────────────────────

def export_lp_irfs() -> None:
    df = pd.read_parquet(PROCESSED / "ro_lp_irfs.parquet")
    records = [
        {
            "outcome": str(r["outcome"]),
            "horizon": int(r["horizon"]),
            "coef": _safe(r["coef"]),
            "se": _safe(r["se"]),
            "ci_lo_90": _safe(r["ci_lo_90"]),
            "ci_hi_90": _safe(r["ci_hi_90"]),
            "ci_lo_95": _safe(r["ci_lo_95"]),
            "ci_hi_95": _safe(r["ci_hi_95"]),
            "nobs": int(r["nobs"]),
        }
        for _, r in df.iterrows()
    ]
    write_json(records, OUT / "lp_irfs.json")


# ── sdid_estimates.json ───────────────────────────────────────────────────────

def export_sdid() -> None:
    df = pd.read_parquet(PROCESSED / "ro_sdid_estimates.parquet")
    records = [
        {
            "outcome": str(r["outcome"]),
            "estimator": str(r["estimator"]),
            "att": _safe(r["att"]),
            "se": _safe(r["se"]),
            "ci_lo": _safe(r["ci_lo"]),
            "ci_hi": _safe(r["ci_hi"]),
            "n_units": int(r["n_units"]),
            "n_years": int(r["n_years"]),
            "pseudo_treat_year": int(r["pseudo_treat_year"]),
        }
        for _, r in df.iterrows()
    ]
    write_json(records, OUT / "sdid_estimates.json")


# ── eventstudy.json ───────────────────────────────────────────────────────────

def export_eventstudy() -> None:
    df = pd.read_parquet(PROCESSED / "ro_eventstudy_coefs.parquet")
    records = [
        {
            "outcome": str(r["outcome"]),
            "event_time": int(r["event_time"]),
            "coef": _safe(r["coef"]),
            "se": _safe(r["se"]),
            "ci_lo": _safe(r["ci_lo"]),
            "ci_hi": _safe(r["ci_hi"]),
        }
        for _, r in df.iterrows()
    ]
    write_json(records, OUT / "eventstudy.json")


# ── summary.json ──────────────────────────────────────────────────────────────

def export_summary() -> None:
    sdid = pd.read_parquet(PROCESSED / "ro_sdid_estimates.parquet")
    suit = pd.read_parquet(PROCESSED / "ro_nuts3_suitability.parquet")
    cities = pd.read_parquet(PROCESSED / "ro_treatment_cities.parquet")
    gaps = pd.read_parquet(PROCESSED / "ro_gsynth_gaps.parquet")

    pop_row = sdid[sdid["outcome"] == "ln_population"]
    att = float(pop_row["att"].iloc[0]) if len(pop_row) else None

    summary = {
        "n_demoted": int((cities["treated"] == 1).sum()),
        "n_tier1": int(suit["tier1_gate"].sum()),
        "reform_year": 2025,
        "sdid_att_ln_pop": _safe(att),
        "sdid_pop_loss_pct": round(att * 100, 1) if att is not None else None,
        "gsc_avg_att": _safe(float(gaps["att_avg_pre"].groupby(gaps["nuts3_code"]).first().mean())),
        "data_note": "SDiD pseudo-treat 2015 (placebo). GSC: 350 PL donors, r*=1.",
    }
    write_json(summary, OUT / "summary.json")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== export_to_json_ro.py ===\n")
    export_regions()
    export_forecasts()
    export_suitability()
    export_lp_irfs()
    export_sdid()
    export_eventstudy()
    export_summary()
    print(f"\nAll JSON written to {OUT}")


if __name__ == "__main__":
    main()
