"""
Stage 04 -- Exploratory Data Analysis.

Reads: data/processed/ro_panel_judet.parquet

Produces (figures/):
  f01_population_trends.png     : ln_population over time, treated vs control means +/-1 SD
  f02_parallel_trends.png       : treated vs control mean for each outcome, 2000-2024
  f03_data_coverage_heatmap.png : NUTS3 x variable coverage heatmap
  f04_pre_reform_distributions.png : violin plots, treated vs control (2020-2024)
  f05_regional_variation.png    : outcome means by NUTS2 region

All figures 300 DPI. Source line included.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "figures"
FIGURES.mkdir(exist_ok=True)

SOURCE_LINE = "Source: Eurostat NUTS3 indicators, 1995-2024. Author's compilation."

OUTCOME_META = {
    "ln_population": ("Log Population", "ln(persons)"),
    "nat_change_rate": ("Natural Change Rate", "per 1 000 inh."),
    "net_migration_rate": ("Net Migration Rate", "per 1 000 inh."),
    "unemployment": ("Unemployment Rate", "%"),
    "ln_gva_per_empl": ("Log GVA per Employed", "ln(EUR)"),
}

PALETTE = {
    "Proposed demoted (treated)": "#d62728",
    "Future regional capital (control)": "#1f77b4",
}


def _add_source(ax: plt.Axes, text: str = SOURCE_LINE) -> None:
    ax.annotate(text, xy=(0, -0.12), xycoords="axes fraction",
                fontsize=6, color="grey", ha="left")


def fig01_population_trends(panel: pd.DataFrame) -> None:
    if "ln_population" not in panel.columns:
        return
    fig, ax = plt.subplots(figsize=(9, 5))
    for tv, label in [(1, "Proposed demoted (treated)"),
                      (0, "Future regional capital (control)")]:
        sub = panel[panel["treated"] == tv]
        agg = sub.groupby("year")["ln_population"].agg(["mean", "std"]).dropna()
        c = PALETTE[label]
        ax.plot(agg.index, agg["mean"], label=label, color=c, lw=2)
        ax.fill_between(agg.index, agg["mean"] - agg["std"],
                        agg["mean"] + agg["std"], alpha=0.15, color=c)
    ax.axvline(2025, ls="--", color="black", lw=1, label="Proposed reform year (2025)")
    ax.set_xlabel("Year")
    ax.set_ylabel("ln(population)")
    ax.set_title("Population Trends: Proposed Demoted vs. Future Regional Capitals",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    _add_source(ax)
    fig.tight_layout()
    out = FIGURES / "f01_population_trends.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


def fig02_parallel_trends(panel: pd.DataFrame) -> None:
    available = [k for k in OUTCOME_META if k in panel.columns]
    if not available:
        return
    n = len(available)
    ncols = min(n, 3)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows), squeeze=False)
    sub_panel = panel[panel["year"] >= 2000].copy()
    for i, col in enumerate(available):
        ax = axes[i // ncols][i % ncols]
        label_str, unit_str = OUTCOME_META[col]
        for tv, label in [(1, "Proposed demoted (treated)"),
                          (0, "Future regional capital (control)")]:
            sub = sub_panel[sub_panel["treated"] == tv]
            agg = sub.groupby("year")[col].mean().dropna()
            ax.plot(agg.index, agg.values, label=label, color=PALETTE[label], lw=1.8)
        ax.axvline(2025, ls="--", color="grey", lw=0.9, alpha=0.7)
        ax.set_title(label_str, fontsize=10)
        ax.set_ylabel(unit_str, fontsize=8)
        ax.set_xlabel("Year", fontsize=8)
        ax.tick_params(labelsize=8)
        ax.grid(axis="y", alpha=0.25)
    for j in range(len(available), nrows * ncols):
        axes[j // ncols][j % ncols].set_visible(False)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2,
               fontsize=9, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Parallel Trends Check: Treated vs. Control Counties (Romania)",
                 fontsize=12, fontweight="bold", y=1.01)
    _add_source(axes[-1][0])
    fig.tight_layout()
    out = FIGURES / "f02_parallel_trends.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


def fig03_coverage_heatmap(panel: pd.DataFrame) -> None:
    cols = [c for c in OUTCOME_META if c in panel.columns]
    if not cols:
        return
    coverage = panel.groupby("nuts3_code")[cols].apply(lambda x: x.notna().mean())
    coverage["total"] = coverage.mean(axis=1)
    coverage = coverage.sort_values("total", ascending=False).drop(columns="total")
    fig, ax = plt.subplots(figsize=(max(6, len(cols) * 1.5), max(8, len(coverage) * 0.3)))
    sns.heatmap(coverage, ax=ax, cmap="YlGn", vmin=0, vmax=1,
                annot=True, fmt=".0%", annot_kws={"size": 6},
                linewidths=0.3, cbar_kws={"label": "Coverage"})
    ax.set_title("Data Coverage by NUTS3 Unit and Variable", fontsize=11, fontweight="bold")
    ax.set_xticklabels([OUTCOME_META.get(c, (c,))[0] for c in coverage.columns],
                       rotation=30, ha="right", fontsize=8)
    ax.set_yticklabels(ax.get_yticklabels(), fontsize=7)
    _add_source(ax)
    fig.tight_layout()
    out = FIGURES / "f03_data_coverage_heatmap.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


def fig04_pre_reform_distributions(panel: pd.DataFrame) -> None:
    cols = [c for c in OUTCOME_META if c in panel.columns]
    if not cols:
        return
    recent = panel[panel["year"].between(2020, 2024)].copy()
    recent["group"] = recent["treated"].map(
        {1: "Proposed demoted", 0: "Future regional capital"}
    )
    ncols = min(len(cols), 3)
    nrows = (len(cols) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows), squeeze=False)
    for i, col in enumerate(cols):
        ax = axes[i // ncols][i % ncols]
        label_str, unit_str = OUTCOME_META[col]
        sub = recent[["group", col]].dropna()
        if sub.empty:
            ax.set_visible(False)
            continue
        sns.violinplot(data=sub, x="group", y=col, hue="group", ax=ax,
                       palette={"Proposed demoted": "#d62728",
                                "Future regional capital": "#1f77b4"},
                       inner="box", cut=0, legend=False)
        ax.set_title(label_str, fontsize=10)
        ax.set_ylabel(unit_str, fontsize=8)
        ax.set_xlabel("")
        ax.tick_params(labelsize=8)
    for j in range(len(cols), nrows * ncols):
        axes[j // ncols][j % ncols].set_visible(False)
    fig.suptitle("Distribution of Outcomes (2020-2024): Treated vs. Control",
                 fontsize=12, fontweight="bold")
    _add_source(axes[-1][0])
    fig.tight_layout()
    out = FIGURES / "f04_pre_reform_distributions.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


def fig05_regional_variation(panel: pd.DataFrame) -> None:
    if "ln_population" not in panel.columns or "nuts2_code" not in panel.columns:
        return
    latest_yr = panel["year"].max()
    latest = panel[panel["year"] == latest_yr].dropna(subset=["ln_population"])
    if latest.empty:
        return
    agg = latest.groupby("nuts2_code")["ln_population"].mean().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(agg.index, agg.values, color="#4c72b0", edgecolor="white", linewidth=0.5)
    ax.set_xlabel("NUTS2 Region")
    ax.set_ylabel("Mean ln(population) across counties")
    ax.set_title(f"Population Size by NUTS2 Region ({latest_yr})",
                 fontsize=11, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    _add_source(ax)
    fig.tight_layout()
    out = FIGURES / "f05_regional_variation.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


def main() -> None:
    print("=== Stage 04: EDA ===\n")
    panel_path = PROCESSED / "ro_panel_judet.parquet"
    if not panel_path.exists():
        raise FileNotFoundError(f"{panel_path} not found -- run 03_merge_panel.py first.")
    panel = pd.read_parquet(panel_path)
    print(f"Loaded panel: {panel.shape} | "
          f"{panel['nuts3_code'].nunique()} units | "
          f"years {panel['year'].min()}-{panel['year'].max()}")

    plt.style.use("seaborn-v0_8-whitegrid")

    print("-- Figure 01: Population trends")
    fig01_population_trends(panel)
    print("-- Figure 02: Parallel trends")
    fig02_parallel_trends(panel)
    print("-- Figure 03: Coverage heatmap")
    fig03_coverage_heatmap(panel)
    print("-- Figure 04: Pre-reform distributions")
    fig04_pre_reform_distributions(panel)
    print("-- Figure 05: Regional variation")
    fig05_regional_variation(panel)
    print("\nAll figures saved to figures/")


if __name__ == "__main__":
    main()
